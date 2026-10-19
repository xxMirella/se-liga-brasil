"""Career coverage receipts and corporate transfers cannot imply unsupported facts."""

from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from crawlers.receita_federal import acquisition
from crawlers.transferegov import normalization
from database.activity_context import PostgresActivityContextRepository
from service.activity_context.linking import ActivityContext, ActivityContextService
from service.ingestion.contracts import IngestionError, Resource
from service.public_career_coverage import assessment, planning
from service.public_career_coverage.contracts import (
    AcquisitionResource,
    CoverageReceipt,
    CoverageScope,
)


def scope(**changes):
    base = CoverageScope(
        "one", "camara", "votes", date(2024, 1, 1), date(2024, 2, 1), "camara", "2024-01"
    )
    return replace(base, **changes)


def test_career_assessment_merges_explicit_expected_scopes_and_database_receipts(monkeypatch):
    facts = {"candidacies": [], "exercises": [], "terms": [{"term_id": 1}]}
    monkeypatch.setattr(assessment, "fetch_career_coverage_inputs", Mock(return_value=facts))
    expected = scope()
    receipt = CoverageReceipt(
        expected, date(2024, 2, 1), True, True, True, True, scope_verified=True
    )
    monkeypatch.setattr(assessment, "fetch_coverage_receipts", Mock(return_value=[receipt]))
    result = assessment.assess_career_coverage(
        "db", ["one"], date(2024, 2, 2), expected_scopes=[expected]
    )
    assert result["assessments"][expected] == "complete_for_period"
    assert result["known_terms"] == facts["terms"] and result["career_beginning_verified"] is False


def test_shared_tse_selection_deduplicates_national_resource_and_restricts_states():
    plan = {
        "resources": [
            AcquisitionResource("tse", "TSE", "elections", "2024/SP", ("one",)),
            AcquisitionResource("tse", "TSE", "elections", "2024/RJ", ("two",)),
            AcquisitionResource("camara", "camara", "votes", "2024-01", ("three",)),
        ]
    }
    national = Resource(
        "r", "national", "https://official.example/national", "candidate", 2024, "d"
    )
    state = replace(national, url="https://official.example/sp", uf="SP", kind="history")
    unrequested = replace(national, url="https://official.example/mg", uf="MG")
    assets = replace(national, kind="asset", url="https://official.example/assets")
    selected = assessment.select_shared_tse_resources(
        plan, [national, national, state, unrequested, assets]
    )
    assert len(selected) == 2
    assert selected[0]["person_ids"] == {"one", "two"}
    assert selected[1]["person_ids"] == {"one"}


@pytest.mark.parametrize(
    ("applicability", "status"), [("unknown", "not_assessed"), ("not_applicable", "not_applicable")]
)
def test_career_scope_unknown_applicability_is_never_complete(applicability, status):
    assert planning.assess_scope(scope(applicability=applicability), [], date(2024, 2, 1)) == status


def test_receipt_cannot_prove_days_after_its_check_date():
    expected = scope()
    receipt = CoverageReceipt(
        expected, date(2024, 1, 15), True, True, True, True, scope_verified=True
    )
    assert planning.assess_scope(expected, [receipt], date(2024, 2, 1)) == "partial"
    assert (
        planning.assess_scope(
            expected, [replace(receipt, checked_on=date(2025, 1, 1))], date(2024, 2, 1)
        )
        == "not_assessed"
    )


def test_unknown_exercise_start_and_future_candidacies_do_not_invent_activity():
    candidacies = [{"person_id": "one", "election_year": 2030, "represented_uf": "SP"}]
    exercises = [{"starts_on": None, "ends_before": None}]
    assert planning.build_observed_scopes(candidacies, exercises, date(2024, 1, 1)) == set()
    assert (
        list(
            planning.build_exercise_scopes(
                {"starts_on": date(2025, 1, 1), "ends_before": None}, date(2024, 1, 1)
            )
        )
        == []
    )


def test_monthly_senate_coverage_requires_both_plenary_and_committee_channels():
    expected = scope(institution="senado", source="senado", domain="offices")
    scopes = planning.build_activity_scopes([expected], domains=("votes",))
    assert {item.partition for item in scopes} == {"plenary/2024-01", "committee/2024-01"}
    assert planning.build_activity_scopes([replace(expected, institution="prefeitura")]) == set()


@pytest.mark.parametrize("verified", [True, False])
def test_activity_context_adapter_uses_parameterized_ownership_validation(verified):
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = {"id": 7} if verified else None
    context = ActivityContext(1, "vote", "proposal:key", "one", 9, datetime(2024, 1, 1, tzinfo=UTC))
    repository = PostgresActivityContextRepository(connection)
    if verified:
        assert repository.link_context(context) == 7
    else:
        with pytest.raises(IngestionError, match="ACTIVITY_CONTEXT_NOT_VERIFIED"):
            repository.link_context(context)
    assert connection.execute.call_args.args[1] == asdict(context)
    assert "canonical_person_id" in connection.execute.call_args.args[0]


@pytest.mark.parametrize("field", ["activity_kind", "external_key", "observed_at", "occurred_at"])
def test_activity_service_rejects_missing_identifiers_and_naive_timestamps(field):
    context = ActivityContext(1, "vote", "key", "one", 9, datetime(2024, 1, 1, tzinfo=UTC))
    value = " " if field in {"activity_kind", "external_key"} else datetime(2024, 1, 1)
    repository = Mock()
    with pytest.raises(IngestionError, match="INVALID_ACTIVITY_"):
        ActivityContextService(repository).link_activity(replace(context, **{field: value}))
    repository.link_context.assert_not_called()


@pytest.mark.parametrize("value", ["2024-02-30T00:00:00", "not-a-date", "2024-01-01T99:99:99"])
def test_transfer_dates_validate_entire_timestamp(value):
    with pytest.raises(IngestionError, match="TRANSFEREGOV_INVALID_DATE"):
        normalization.normalize_api_date(value)


def test_transfer_organization_requires_document_length_but_allows_name_only():
    assert normalization.normalize_organization({}, "executor", "executor") is None
    assert normalization.normalize_organization(
        {"nm_executor": "Hospital Municipal"}, "executor", "executor"
    ) == {"role": "executor", "corporate_document": None, "name": "Hospital Municipal"}
    with pytest.raises(IngestionError, match="TRANSFEREGOV_INVALID_CNPJ_LENGTH"):
        normalization.normalize_organization({"cnpj_executor": "123"}, "executor", "executor")


def test_special_transfer_and_amendment_never_guess_person_from_external_ids():
    action = normalization.normalize_special_action(
        {"id_plano_acao": "123", "valor_custeio_plano_acao": "1.25"}
    )
    indication = normalization.normalize_amendment_indication(
        {"id_indicacao_beneficiario_emenda_parlamentar": "99"}
    )
    assert action["operating_amount"] == "1.25"
    assert action["person_id"] is None and indication["person_id"] is None
    assert (
        action["person_link_status"]
        == indication["person_link_status"]
        == "requires_reviewed_identity"
    )


@pytest.mark.parametrize(
    ("month", "url", "error"),
    [
        ("2024-13", "", "CNPJ_INVALID_SNAPSHOT_MONTH"),
        (
            "2024-01",
            "https://dadosabertos.rfb.gov.br/2024-01/Other.zip",
            "CNPJ_UNSUPPORTED_PARTITION",
        ),
        (
            "2024-01",
            "https://dadosabertos.rfb.gov.br/2024-02/Empresas0.zip",
            "CNPJ_SNAPSHOT_URL_MISMATCH",
        ),
        (
            "2024-01",
            "https://dadosabertos.rfb.gov.br/2024-01/Empresas0.zip?x=1",
            "CNPJ_UNSUPPORTED_PARTITION",
        ),
    ],
)
def test_corporate_snapshot_rejects_unbounded_or_wrong_partition(month, url, error):
    with pytest.raises(IngestionError, match=error):
        acquisition.plan_resources(month, [url], SimpleNamespace(max_resources=3))


def test_corporate_snapshot_deduplicates_and_shares_budget_across_downloads(monkeypatch):
    url = "https://dadosabertos.rfb.gov.br/2024-01/Empresas0.zip"
    config = SimpleNamespace(max_resources=2)
    resources = acquisition.plan_resources(
        "2024-01", [url, url, url.replace("Empresas", "Socios")], config
    )
    assert [row.kind for row in resources] == ["companies", "partners"]
    download = Mock(side_effect=lambda resource, configuration, client, budget: resource)
    monkeypatch.setattr(acquisition, "download_resource", download)
    assert list(acquisition.acquire_resources(resources, config, "client")) == list(resources)
    assert download.call_args_list[0].args[-1] is download.call_args_list[1].args[-1]
    with pytest.raises(IngestionError, match="CNPJ_RESOURCE_LIMIT_EXCEEDED"):
        list(acquisition.acquire_resources(resources, SimpleNamespace(max_resources=1), "client"))
    with pytest.raises(IngestionError, match="CNPJ_RESOURCE_LIMIT_EXCEEDED"):
        acquisition.plan_resources(
            "2024-01", [row.url for row in resources], SimpleNamespace(max_resources=1)
        )
