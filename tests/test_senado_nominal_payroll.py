"""Nominal salaries require independently verified identity and exact monthly accounting."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from crawlers.senado.payroll import (
    MONEY_FIELDS,
    index_monthly_payroll,
    index_parliamentary_recipients,
    normalize_monthly_salary,
)
from crawlers.senado.payroll_acquisition import (
    index_payroll_names,
    match_payroll_entries,
    previous_payroll_period,
)
from crawlers.senado.payroll_pipeline import shared_payroll_snapshot
from service.ingestion.contracts import IngestionError

PERIOD = date(2026, 9, 1)
PROFILE = {"personId": "canonical-person", "civilName": "Pessoa Exemplo", "representedUf": "PA"}


def payroll_row(**changes):
    return (
        dict.fromkeys(MONEY_FIELDS, "0,00")
        | {
            "sequencial": 77,
            "nome": "PESSOA EXEMPLO",
            "ano": 2026,
            "mes": 9,
            "tipo_folha": "Normal",
            "remuneracao_basica": "1.000,00",
            "imposto_renda": "-100,00",
            "previdencia": "-50,00",
            "faltas": "-20,00",
            "remuneracao_liquida": "830,00",
            "diarias": "900,00",
        }
        | changes
    )


def snapshot(rows=None, registry=None):
    entries = index_monthly_payroll(rows if rows is not None else [payroll_row()], PERIOD)
    registry = (
        registry
        if registry is not None
        else [
            {
                "sequencial": 999,
                "nome": "Pessoa Exemplo",
                "vinculo": "PARLAMENTAR",
                "situacao": "ATIVO",
            }
        ]
    )
    return SimpleNamespace(
        period=PERIOD,
        entries_by_recipient=entries,
        recipients_by_name=index_parliamentary_recipients(registry),
        payroll_recipients_by_name=index_payroll_names(entries),
    )


def test_registry_and_payroll_sequences_are_distinct_namespaces():
    snap = snapshot()
    key, rows = match_payroll_entries(snap, PROFILE)
    assert key == "77" and snap.recipients_by_name["pessoa exemplo"] == {"999"}
    salary = normalize_monthly_salary(rows, PROFILE, key, PERIOD)
    assert salary["recipientKey"] == PROFILE["personId"]
    assert salary["payrollRecipientSequence"] == "77"
    assert salary["recipientName"] == "PESSOA EXEMPLO"


def test_normal_and_supplementary_payments_sum_without_losing_repeated_entries():
    extra = payroll_row(
        tipo_folha="Suplementar",
        remuneracao_basica="200,00",
        imposto_renda="-20,00",
        previdencia="-10,00",
        faltas="0,00",
        remuneracao_liquida="170,00",
    )
    rows = index_monthly_payroll([payroll_row(), extra, extra], PERIOD)["77"]
    salary = normalize_monthly_salary(rows, PROFILE, "77", PERIOD)
    assert (salary["grossAmount"], salary["taxAmount"], salary["netAmount"]) == (
        "1380.00",
        "210.00",
        "1170.00",
    )
    assert len(salary["payrollEntries"]) == 3
    assert salary["payrollEntries"][0]["components"]["diarias"] == "900.00"


@pytest.mark.parametrize(
    "change,code",
    [
        ({"remuneracao_liquida": "831,00"}, "RECONCILIATION_FAILED"),
        ({"imposto_renda": None}, "REQUIRED_VALUE_MISSING"),
        ({"nome": "Outra Pessoa"}, "PERSON_MISMATCH"),
        ({"tipo_folha": "Desconhecida"}, "KIND_NOT_SUPPORTED"),
    ],
)
def test_invalid_payment_is_not_converted_into_verified_salary(change, code):
    with pytest.raises(IngestionError, match=code):
        normalize_monthly_salary([(1, payroll_row(**change))], PROFILE, "77", PERIOD)


def test_supplementary_only_does_not_claim_a_complete_regular_salary():
    with pytest.raises(IngestionError, match="REGULAR_PAYROLL_NOT_PUBLISHED"):
        normalize_monthly_salary(
            [(1, payroll_row(tipo_folha="Suplementar"))], PROFILE, "77", PERIOD
        )


def test_homonymous_payroll_recipients_are_never_merged():
    snap = snapshot([payroll_row(), payroll_row(sequencial=78)])
    with pytest.raises(IngestionError, match="NAME_AMBIGUOUS"):
        match_payroll_entries(snap, PROFILE)


def test_registry_homonyms_and_absent_payments_remain_unresolved():
    reg = [
        {"sequencial": i, "nome": "Pessoa Exemplo", "vinculo": "PARLAMENTAR", "situacao": "ATIVO"}
        for i in (1, 2)
    ]
    with pytest.raises(IngestionError, match="IDENTITY_NOT_CONFIRMED"):
        match_payroll_entries(snapshot(registry=reg), PROFILE)
    with pytest.raises(IngestionError, match="PERSON_NOT_PUBLISHED"):
        match_payroll_entries(snapshot([]), PROFILE)


@pytest.mark.parametrize(
    "change,code",
    [
        ({"ano": 2025}, "REFERENCE_MISMATCH"),
        ({"mes": 8}, "REFERENCE_MISMATCH"),
        ({"sequencial": True}, "RECIPIENT_ID_INVALID"),
        ({"sequencial": -1}, "RECIPIENT_ID_INVALID"),
    ],
)
def test_schema_rejects_wrong_competence_and_invalid_identifiers(change, code):
    with pytest.raises(IngestionError, match=code):
        index_monthly_payroll([payroll_row(**change)], PERIOD)


def test_one_payroll_sequence_cannot_identify_two_names():
    with pytest.raises(IngestionError, match="RECIPIENT_CONFLICT"):
        index_monthly_payroll([payroll_row(), payroll_row(nome="Outra Pessoa")], PERIOD)


def test_registry_does_not_accept_staff_as_parliamentarians():
    with pytest.raises(IngestionError, match="SCOPE_MISMATCH"):
        index_parliamentary_recipients([{"sequencial": 1, "vinculo": "COMISSIONADO"}])


def test_previous_competence_handles_year_boundary():
    assert previous_payroll_period(date(2026, 1, 22)) == date(2025, 12, 1)
    assert previous_payroll_period(date(2026, 3, 1)) == date(2026, 2, 1)


def test_monthly_download_and_failed_source_are_shared_between_people(monkeypatch):
    from crawlers.senado import payroll_pipeline

    acquire = Mock(return_value="one snapshot")
    monkeypatch.setattr(payroll_pipeline, "acquire_monthly_payroll", acquire)
    acquisition = SimpleNamespace(payroll_snapshot=None, payroll_error=None)
    assert shared_payroll_snapshot(acquisition) == shared_payroll_snapshot(acquisition)
    acquire.assert_called_once()
    acquisition = SimpleNamespace(payroll_snapshot=None, payroll_error=None)
    acquire.reset_mock(side_effect=True)
    acquire.side_effect = IngestionError("HTTP_ERROR", {"status": 429})
    for _ in range(2):
        with pytest.raises(IngestionError, match="HTTP_ERROR"):
            shared_payroll_snapshot(acquisition)
    acquire.assert_called_once()


def test_nominal_snapshot_downloads_registry_and_payroll_once_using_published_api(monkeypatch):
    from crawlers.senado import payroll_acquisition

    monkeypatch.setattr(payroll_acquisition, "previous_payroll_period", lambda: PERIOD)
    registry = [
        {"sequencial": 999, "nome": "Pessoa Exemplo", "vinculo": "PARLAMENTAR", "situacao": "ATIVO"}
    ]
    acquisition = Mock()
    acquisition.json_document.side_effect = [
        (registry, "registry-artifact"),
        ([payroll_row()], "payroll-artifact"),
    ]
    snap = payroll_acquisition.acquire_monthly_payroll(acquisition)
    assert snap.source_rows == 1 and snap.period == PERIOD
    assert len(acquisition.json_document.call_args_list) == 2
    call = acquisition.json_document.call_args_list[1]
    assert call.args[0].endswith("/servidores/remuneracoes/2026/9")
    assert call.kwargs == {"resource_year": 2026}


def test_unverified_profile_never_downloads_payroll():
    from crawlers.senado.payroll_pipeline import collect_verified_salary

    acquisition = Mock()
    with pytest.raises(IngestionError, match="PROFILE_NOT_VERIFIED"):
        collect_verified_salary(None, acquisition, PROFILE)
    acquisition.json_document.assert_not_called()


def test_salary_pipeline_stages_only_requested_person_and_preserves_both_sequence_namespaces(
    monkeypatch,
):
    from crawlers.senado import payroll_pipeline
    from service.ingestion.contracts import IngestionSummary

    snap = snapshot()
    snap.payroll_artifact = "original-payroll"
    snap.registry_artifact = SimpleNamespace(
        resource=SimpleNamespace(url="https://adm.senado.gov.br"), sha256="a" * 64
    )
    snap.source_rows = 10754
    acquisition = SimpleNamespace(
        payroll_snapshot=snap, payroll_error=None, configuration=SimpleNamespace(batch_size=500)
    )
    stage = Mock(return_value="validated")
    monkeypatch.setattr(payroll_pipeline, "stage_records", stage)
    repository = Mock()
    repository.ingest_validated_artifact.return_value = IngestionSummary(new=1)
    profile = PROFILE | {"identityMethod": "unique_full_name_birth_date"}
    result = payroll_pipeline.collect_verified_salary(repository, acquisition, profile)
    assert result["new"] == 1 and result["source_rows"] == 10754
    salary = stage.call_args.args[2][0]
    assert salary["payrollRecipientSequence"] == "77"
    assert salary["administrativeRegistrySequence"] == "999"
    assert salary["personId"] == "canonical-person"
    repository.ingest_validated_artifact.assert_called_once_with("validated", 500)
