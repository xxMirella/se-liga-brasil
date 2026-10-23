"""Institutional payroll discovery and party changes require explicit source evidence."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from crawlers.alerj import payroll as alerj_payroll
from crawlers.alesp import discovery
from database import political_party_verification as party_database
from service.identity_resolution import payroll as identity_payroll
from service.identity_resolution.matching import PersonIdentityCandidate
from service.ingestion.contracts import IngestionError
from service.political_party_verification import changes
from storage.files import load_json


def payroll_link(month="01", host="www.al.sp.gov.br"):
    return f"https://{host}/repositorio/folha-de-pagamento/folha-deputados-2024-{month}.html"


def test_payroll_discovery_deduplicates_and_sorts_published_months():
    payload = (
        f'<a href="{payroll_link("02")}">Feb</a><a href="{payroll_link()}">Jan</a>'
        f'<a href="{payroll_link()}">Duplicate</a><a href="/other">Ignore</a>'
    )
    resources = discovery.parse_payroll_resources(payload.encode())
    assert [discovery.payroll_month(row) for row in resources] == ["2024-01", "2024-02"]
    config = SimpleNamespace(years=(2024,), months=("2024-02",))
    assert not discovery.is_selected_resource(resources[0], config)
    assert discovery.is_selected_resource(resources[1], config)
    assert not discovery.is_selected_resource(
        resources[1], SimpleNamespace(years=(2020,), months=())
    )


@pytest.mark.parametrize(
    ("url", "error"),
    [
        (payroll_link("13"), "INVALID_PAYROLL_MONTH"),
        (payroll_link(host="untrusted.example"), "UNTRUSTED_RESOURCE_URL"),
    ],
)
def test_payroll_discovery_rejects_invalid_month_and_untrusted_host(url, error):
    with pytest.raises(IngestionError, match=error):
        discovery.parse_payroll_resources(f'<a href="{url}">Month</a>'.encode())


def test_payroll_discovery_preserves_original_index_and_manifest(tmp_path):
    config = SimpleNamespace(
        storage_directory=tmp_path, years=(), months=(), max_download_bytes=4096
    )
    client = Mock()
    client.fetch_bytes.return_value = f'<a href="{payroll_link()}">Jan</a>'.encode()
    result = discovery.discover_resources(config, client)
    assert len(result) == 1
    manifest = load_json(tmp_path / "catalog-manifest.json")
    assert (tmp_path / "catalogs" / (manifest["sha256"] + ".html")).read_bytes() == (
        client.fetch_bytes.return_value
    )
    config.months = ("2024-12",)
    with pytest.raises(IngestionError, match="NO_PUBLISHED_PAYROLL_RESOURCES"):
        discovery.discover_resources(config, client)


@pytest.mark.parametrize(
    ("available", "returncode", "code"),
    [
        (None, 0, "ALERJ_PDF_EXTRACTOR_UNAVAILABLE"),
        ("/usr/bin/pdftotext", 1, "ALERJ_PDF_EXTRACTION_FAILED"),
    ],
)
def test_payroll_pdf_extractor_fails_explicitly(monkeypatch, available, returncode, code):
    monkeypatch.setattr(alerj_payroll.shutil, "which", Mock(return_value=available))
    run = Mock(return_value=SimpleNamespace(returncode=returncode))
    monkeypatch.setattr(alerj_payroll.subprocess, "run", run)
    with pytest.raises(IngestionError, match=code):
        alerj_payroll.extract_pdf_text("source.pdf")
    if available is None:
        run.assert_not_called()


def test_payroll_pdf_extractor_uses_argument_array_timeout_and_utf8(monkeypatch):
    monkeypatch.setattr(alerj_payroll.shutil, "which", Mock(return_value="/usr/bin/pdftotext"))
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout="Competência".encode()))
    monkeypatch.setattr(alerj_payroll.subprocess, "run", run)
    assert alerj_payroll.extract_pdf_text("source file.pdf") == "Competência"
    assert run.call_args.args[0] == ["/usr/bin/pdftotext", "-layout", "source file.pdf", "-"]
    assert run.call_args.kwargs["timeout"] == 60


def test_payroll_parser_requires_competence_and_deputy_rows():
    with pytest.raises(IngestionError, match="ALERJ_PAYROLL_COMPETENCE_MISSING"):
        alerj_payroll.parse_deputy_payroll("unrelated")
    with pytest.raises(IngestionError, match="ALERJ_NO_DEPUTY_PAYROLL_ROWS"):
        alerj_payroll.parse_deputy_payroll("Folha de Pagamento de Janeiro de 2024\nOther employee")
    row = "  ".join(["Pessoa Exemplo", "DEPUTADO ESTADUAL", *(["0,00"] * 14)])
    with pytest.raises(IngestionError, match="ALERJ_DUPLICATE_PAYROLL_RECIPIENT"):
        alerj_payroll.parse_deputy_payroll(
            "Folha de Pagamento de Janeiro de 2024\n" + row + "\n" + row
        )
    assert alerj_payroll.parse_amount("-") == Decimal("0.00")


def test_party_change_requires_date_in_change_interval_and_separates_people():
    observations = [
        {
            "person_id": "one",
            "competence": "2024-02-01",
            "political_party_code": "02",
            "source_record_id": 2,
        },
        {
            "person_id": "two",
            "competence": "2024-02-01",
            "political_party_code": "02",
            "source_record_id": 3,
        },
        {
            "person_id": "one",
            "competence": "2024-01-01",
            "political_party_code": "01",
            "source_record_id": 1,
        },
    ]
    reports = [
        {
            "person_id": "one",
            "political_party_code": "02",
            "starts_on": "2024-02-29",
            "source_record_id": 9,
        },
        {
            "person_id": "two",
            "political_party_code": "02",
            "starts_on": None,
            "source_record_id": 8,
        },
    ]
    results = changes.verify_monthly_political_parties(observations, reports)
    assert [row["status"] for row in results] == [
        "initial_observation",
        "reported_change_confirmed",
        "initial_observation",
    ]
    assert results[1]["verification_through"] == "2024-02-29"
    assert results[1]["evidence_source_record_ids"] == [9]
    reports[0]["starts_on"] = "2024-03-01"
    assert changes.verify_monthly_political_parties(observations, reports)[1]["status"] == (
        "change_requires_verification"
    )


def test_party_database_without_observations_cannot_claim_verified_change():
    connection = Mock()
    connection.execute.return_value.fetchall.return_value = []
    assert party_database.verify_payroll_political_parties(connection, 1, "source") == {
        "status": "source_does_not_report_political_party",
        "observations": 0,
    }
    assert connection.execute.call_count == 1
    party_database.persist_party_evidence(connection, 1, "source", [], "field")
    assert connection.execute.call_count == 1


def test_party_database_verification_persists_source_evidence_without_duplicate_writes():
    connection = Mock()
    observations = [
        {
            "person_id": "one",
            "competence": "2024-01-01",
            "political_party_code": "01",
            "source_record_id": 1,
        }
    ]
    connection.execute.return_value.fetchall.side_effect = [observations, []]
    result = party_database.verify_payroll_political_parties(
        connection, 3, "https://official.example"
    )
    assert result == {"observations": 1, "statuses": {"initial_observation": 1}}
    payload = connection.execute.call_args.kwargs or connection.execute.call_args.args[1]
    assert payload["items"].obj[0]["source_record_id"] == 1
    assert payload["field_name"] == "political_party_change_verification"
    assert "ON CONFLICT DO NOTHING" in connection.execute.call_args.args[0]


@pytest.mark.parametrize("reviewed", [False, True])
def test_payroll_identity_resolution_applies_review_only_when_explicitly_supplied(
    monkeypatch, reviewed
):
    candidates = [PersonIdentityCandidate("one", {"pessoa exemplo"})]
    monkeypatch.setattr(
        identity_payroll, "fetch_electoral_identity_candidates", Mock(return_value=candidates)
    )
    monkeypatch.setattr(
        identity_payroll,
        "fetch_payroll_recipients",
        Mock(
            return_value=[
                {"recipient_key": "key", "recipient_name": "Pessoa Exemplo"},
                {"recipient_key": "unmatched", "recipient_name": "Outra Pessoa"},
            ]
        ),
    )
    monkeypatch.setattr(identity_payroll, "build_identity_links", Mock(return_value=["link"]))
    monkeypatch.setattr(identity_payroll, "save_payroll_identity_reviews", Mock())
    apply_links = Mock(return_value={"linked": 1})
    monkeypatch.setattr(identity_payroll, "apply_payroll_identity_links", apply_links)
    fetch_reviewed = Mock(return_value={})
    monkeypatch.setattr(identity_payroll, "fetch_reviewed_people", fetch_reviewed)
    crosswalk = Mock(side_effect=lambda resolutions, recipients, cases, targets: resolutions)
    monkeypatch.setattr(identity_payroll, "apply_reviewed_crosswalk", crosswalk)
    cases = [{"scope": "SP"}] if reviewed else []
    result = identity_payroll.resolve_payroll_identities(
        "db", 3, "url", [], uf="SP", office_code="7", reviewed_cases=cases
    )
    assert result["recipients"] == 2 and result["unresolved_recipients"] == 2
    assert result["linked"] == 1
    assert crosswalk.called is reviewed and fetch_reviewed.called is reviewed
    apply_links.assert_called_once_with("db", 3, ["link"], "url")
