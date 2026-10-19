"""Progress works with streamed bytes, failures, and redirected output."""

import io
import json
from datetime import UTC, datetime, timedelta

import httpx

from crawlers.tse.downloader import download_resource
from crawlers.tse.http_client import OfficialHttpClient
from service.crawling import tse_pipeline
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from service.observability.download_progress import DownloadProgress
from storage.files import load_json, save_json


class TerminalBuffer(io.StringIO):
    def isatty(self):
        return True


def test_terminal_bar_shows_bytes_and_remaining_without_invented_percentage(capsys):
    terminal = TerminalBuffer()
    progress = DownloadProgress(2, terminal)
    progress.start_file("Candidatos PA")
    progress.last_refresh = 0
    progress.update_bytes(1024, None)
    assert "tamanho desconhecido" in terminal.getvalue()
    progress.update_bytes(2048, 2048)
    assert "100%" in terminal.getvalue()
    assert "faltam 2" in terminal.getvalue()
    progress.finish_file(True)
    progress.start_file("Bens PA")
    progress.finish_file(False)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1] == {
        "phase": "download_progress",
        "total_files": 2,
        "completed": 1,
        "failed": 1,
        "cached": 0,
        "downloaded": 1,
        "remaining": 0,
    }


def test_redirected_progress_has_no_terminal_escape_codes(capsys):
    output = io.StringIO()
    progress = DownloadProgress(1, output)
    progress.start_file("Arquivo")
    progress.update_bytes(10, 10)
    progress.finish_file(True)
    assert output.getvalue() == ""
    assert "\x1b" not in capsys.readouterr().out


def test_stream_download_reports_received_bytes(configuration):
    resource = Resource(
        "progress", "Arquivo", "https://cdn.tse.jus.br/a.zip", "candidate", 2026, "candidatos-2026"
    )
    data = b"x" * (1024 * 1024 + 10)
    updates = []
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=data))
    with httpx.Client(transport=transport) as client:
        artifact = download_resource(
            resource,
            configuration,
            OfficialHttpClient(configuration, client),
            DownloadBudget(),
            lambda received, expected: updates.append((received, expected)),
        )
    assert updates == [(1024 * 1024, len(data)), (len(data), len(data))]
    assert artifact.path.read_bytes() == data


def test_failed_resource_does_not_stop_progress_or_hide_total(configuration, monkeypatch, capsys):
    resources = [
        Resource(
            str(index),
            "Arquivo",
            "https://cdn.tse.jus.br/a.zip",
            "candidate",
            2026,
            "candidatos-2026",
        )
        for index in range(2)
    ]

    def fail_download(*arguments):
        raise IngestionError("HTTP_ERROR", {"status": 503})

    monkeypatch.setattr("service.crawling.acquisition.download_resource", fail_download)
    downloads, failures = tse_pipeline.download_selected_resources(configuration, None, resources)
    assert downloads == []
    assert len(failures) == 2
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[0] == {"phase": "discovery", "total_files": 2}
    assert events[-1]["remaining"] == 0
    assert events[-1]["failed"] == 2


def test_resume_skips_intact_files_and_redownloads_missing_corrupt_or_expired(configuration):
    resource = Resource(
        "resume", "Arquivo", "https://cdn.tse.jus.br/a.zip", "candidate", 2026, "candidatos-2026"
    )
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, content=f"version-{len(requests)}".encode())

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        official = OfficialHttpClient(configuration, client)
        first = download_resource(resource, configuration, official, DownloadBudget())
        assert first.acquisition_status == "downloaded"
        budget = DownloadBudget()
        cached = download_resource(resource, configuration, official, budget)
        assert cached.acquisition_status == "cached"
        assert len(requests) == 1
        assert budget.bytes_used == 0
        cached.path.unlink()
        missing = download_resource(resource, configuration, official, DownloadBudget())
        assert len(requests) == 2
        missing.path.write_bytes(b"corrupted")
        download_resource(resource, configuration, official, DownloadBudget())
        assert len(requests) == 3
        manifest_path = configuration.storage_directory / "manifests/resume.json"
        manifest = load_json(manifest_path)
        old_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        save_json(
            manifest_path, manifest | {"checked_at": old_time, "last_full_check_at": old_time}
        )
        updated = download_resource(resource, configuration, official, DownloadBudget())
        assert len(requests) == 4
        assert updated.sha256 != first.sha256
