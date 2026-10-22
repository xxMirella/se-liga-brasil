"""Financial source collection is bounded, records provenance, and releases its source lock."""

import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_senado_cabinet_payroll import payroll_csv, staff_row

from crawlers.senado import cabinet_collection as collection
from service.ingestion.contracts import IngestionError, IngestionSummary


@pytest.fixture
def cabinet_source(monkeypatch, tmp_path):
    repository = Mock()
    repository.ingest_validated_artifact.return_value = IngestionSummary(new=1)
    monkeypatch.setattr(collection, "IngestionRepository", lambda *a, **kw: repository)
    person = {"person_id": "person", "civil_name": "Pessoa Civil", "source_record_id": 123}
    monkeypatch.setattr(collection, "fetch_verified_senate_people", lambda _: [person])
    member = {
        "IdentificacaoParlamentar": {
            "NomeCompletoParlamentar": "Pessoa Civil",
            "NomeParlamentar": "Pessoa Exemplo",
        }
    }
    roster = {"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": [member]}}}
    payloads = {
        "senado_staff_payroll_index": b'<a href="/transparencia/LAI/secrh/'
        b'SF_ConsultaRemuneracaoServidoresParlamentares_202609.csv">Month</a>',
        "senado_roster": json.dumps(roster).encode(),
        "senado_cabinet_payroll": payroll_csv([staff_row()]),
    }

    def acquire(configuration, transport, budget, url, kind, suffix):
        path = tmp_path / (kind + suffix)
        path.write_bytes(payloads[kind])
        return SimpleNamespace(
            path=path,
            sha256="a" * 64,
            fetched_at="2026-10-22T12:00:00Z",
            resource=SimpleNamespace(url=url),
        )

    monkeypatch.setattr(collection, "acquire_document", acquire)
    stage = Mock(return_value="validated")
    monkeypatch.setattr(collection, "stage_cabinet_payroll", stage)
    return repository, stage, payloads


def test_month_uses_verified_cabinet_and_stores_roster_provenance(cabinet_source, tmp_path):
    repository, stage, _ = cabinet_source
    result = collection.collect_cabinet_payroll(None, tmp_path, maximum=1)
    assert result["status"] == "completed" and result["verified_cabinets"] == 1
    data = stage.call_args.args[2][0]
    assert data["total_amount"] == "1200.00"
    assert data["identityEvidence"]["profileSourceRecordId"] == 123
    assert data["identityEvidence"]["roster"]["sha256"] == "a" * 64
    repository.finish_run.assert_called_once_with("completed", result)


def test_unverified_cabinet_does_not_receive_financial_facts(cabinet_source, tmp_path):
    repository, stage, payloads = cabinet_source
    payloads["senado_cabinet_payroll"] = payroll_csv(
        [staff_row(**{"LOTAÇÃO EXERCÍCIO": "Gabinete do Senador Outro Nome"})]
    )
    with pytest.raises(IngestionError, match="IDENTITY_NOT_CONFIRMED"):
        collection.collect_cabinet_payroll(None, tmp_path, maximum=1)
    stage.assert_not_called()
    repository.finish_run.assert_called_once_with("failed", {"months": []})


def test_rejected_month_and_missing_other_cabinet_are_explicitly_partial(cabinet_source, tmp_path):
    repository, _, payloads = cabinet_source
    repository.ingest_validated_artifact.return_value = IngestionSummary(rejected=1)
    payloads["senado_cabinet_payroll"] = payroll_csv(
        [staff_row(), staff_row(**{"LOTAÇÃO EXERCÍCIO": "Gabinete do Senador Outro Nome"})]
    )
    result = collection.collect_cabinet_payroll(None, tmp_path, maximum=1)
    assert result["status"] == "partial"
    assert result["months"][0]["unmatched_cabinets"] == 1


def test_cli_collects_only_explicit_month_budget(monkeypatch, tmp_path):
    from application import cabinet_payroll
    from application.cli import create_argument_parser, execute_command

    monkeypatch.setattr(cabinet_payroll, "connect_database", lambda _: nullcontext(None))
    collect = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(cabinet_payroll, "collect_cabinet_payroll", collect)
    arguments = create_argument_parser().parse_args(
        [
            "collect-cabinet-payroll",
            "--months",
            "2026-09,2026-08",
            "--max-partitions",
            "2",
            "--storage-directory",
            str(tmp_path),
        ]
    )
    assert execute_command(arguments) == {"status": "completed"}
    assert collect.call_args.kwargs["maximum"] == 2
    assert collect.call_args.args[2] == ["2026-09", "2026-08"]
