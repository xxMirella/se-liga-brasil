"""National scope and actionable, non-sensitive failure reporting."""

import json

from application import cli
from crawlers.tse.configuration import load_configuration
from service.crawling.tse_pipeline import build_resource_failure
from service.ingestion.contracts import IngestionError, Resource


def test_all_states_override_restricted_configuration(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "years": [2026],
                "ufs": ["PA"],
                "kinds": ["candidate"],
                "storage_directory": str(tmp_path / "data"),
            }
        ),
        encoding="utf-8",
    )
    arguments = cli.create_argument_parser().parse_args(["run", "--ufs", "all"])
    configuration = load_configuration(config_path, cli.parse_scope_overrides(arguments))
    assert configuration.ufs == ()
    assert configuration.scope_key == "all"


def test_resource_failure_identifies_stage_resource_and_code_location(capsys):
    resource = Resource(
        "official-id",
        "Bens PA",
        "https://cdn.tse.jus.br/bens.zip",
        "asset",
        2026,
        "candidatos-2026",
        "PA",
    )
    try:
        raise IngestionError("CSV_SCHEMA_CHANGED", {"missing_headers": ["SQ_CANDIDATO"]})
    except IngestionError as error:
        failure = build_resource_failure(resource, error, "validate")
    assert failure["stage"] == "validate"
    assert failure["uf"] == "PA"
    assert failure["source_url"] == resource.url
    assert failure["missing_headers"] == ["SQ_CANDIDATO"]
    assert failure["location"]["function"] == (
        "test_resource_failure_identifies_stage_resource_and_code_location"
    )
    assert failure["location"]["line"] > 0
    assert "colunas esperadas" in failure["message"]
    assert json.loads(capsys.readouterr().err)["phase"] == "resource_failed"


def test_unexpected_error_exits_nonzero_without_exposing_exception_values(monkeypatch, capsys):
    def raise_database_failure(arguments):
        raise RuntimeError("postgresql://user:secret@private-host/database")

    monkeypatch.setattr(cli, "execute_command", raise_database_failure)
    monkeypatch.setattr("sys.argv", ["se-liga-brasil", "run", "--ufs", "all"])
    assert cli.main() == 1
    output = capsys.readouterr().err
    assert "secret" not in output
    failure = json.loads(output)
    assert failure["command"] == "run"
    assert failure["error_type"] == "RuntimeError"
    assert failure["location"]["function"] == "raise_database_failure"
