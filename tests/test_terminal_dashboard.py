"""Terminal events stay in one panel and rejection reasons survive in private logs."""

import io

from service.crawling.tse_pipeline import validate_downloaded_resources
from service.observability.reporting import emit_event
from service.observability.run_reporter import RunReporter
from storage.files import read_json_lines


class TerminalBuffer(io.StringIO):
    def isatty(self):
        return True


def test_single_panel_suppresses_scrolling_json_and_counts_unique_rejected_files(tmp_path, capsys):
    terminal = TerminalBuffer()
    with RunReporter(tmp_path, terminal) as reporter:
        emit_event("discovery", total_files=2)
        for stage in ("validate", "ingest"):
            emit_event(
                "rejected",
                stage=stage,
                resource_id="one",
                entry_name="candidatos.csv",
                row_number=12,
                code="INVALID_DATE",
                message="Data inválida.",
            )
        emit_event("finished", status="partial")
        assert len(reporter.rejected_files) == 1
    output = terminal.getvalue()
    assert "\033[9A" in output
    assert "Arquivos com rejeições/falhas: 1" in output
    assert "Data inválida." in output
    assert '"phase"' not in output
    assert capsys.readouterr().out == ""
    rejections = list(read_json_lines(reporter.log_path))
    assert len(rejections) == 2
    assert rejections[0]["entry_name"] == "candidatos.csv"
    assert rejections[0]["row_number"] == 12
    assert rejections[0]["timestamp"]
    assert reporter.log_path.stat().st_mode & 0o777 == 0o600
    assert not reporter.refresh_thread.is_alive()


def test_validation_logs_actual_rejection_reason_and_row(
    configuration, archive_factory, candidate_row, capsys
):
    artifact = archive_factory("candidate", [candidate_row | {"DT_NASCIMENTO": "31/02/2000"}])
    with RunReporter(configuration.storage_directory, TerminalBuffer()) as reporter:
        validations, failures = validate_downloaded_resources(configuration, [artifact])
    assert not failures
    assert validations[0].summary["rejected"] == 1
    rejection = list(read_json_lines(reporter.log_path))[0]
    assert rejection["code"] == "INVALID_DATE"
    assert "formato esperado" in rejection["message"]
    assert rejection["row_number"] == 2
    assert rejection["entry_name"].endswith(".csv")
    assert rejection["resource_id"] == artifact.resource.resource_id
    assert rejection["context"]["candidate_name"] == candidate_row["NM_CANDIDATO"]
    assert rejection["context"]["candidate_sequence"] == candidate_row["SQ_CANDIDATO"]
    assert rejection["context"]["candidate_source"]["row_number"] == 2
    assert "NR_CPF_CANDIDATO" not in str(rejection)
    assert capsys.readouterr().out == ""


def test_completion_message_survives_dashboard_and_reports_partial_results(tmp_path):
    terminal = TerminalBuffer()
    with RunReporter(tmp_path, terminal):
        emit_event(
            "finished",
            status="partial",
            failures=[],
            artifacts=[{"new": 3, "rejected": 2}],
            rejection_log="private/log.ndjson",
        )
    output = terminal.getvalue()
    assert "FINALIZADO COM PENDÊNCIAS" in output
    assert "Registros aceitos: 3 | Rejeitados: 2" in output
    assert "todos os dados válidos" not in output


def test_completed_run_explicitly_announces_all_valid_data(tmp_path):
    terminal = TerminalBuffer()
    with RunReporter(tmp_path, terminal):
        emit_event("finished", status="completed", failures=[], artifacts=[{"new": 3}])
    assert "todos os dados válidos encontrados foram ingeridos" in terminal.getvalue()
