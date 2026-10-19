from datetime import UTC, datetime, timedelta

import httpx
import pytest

from code_quality.system_design import review_python_file
from crawlers.tse.downloader import download_resource
from crawlers.tse.http_client import OfficialHttpClient, validate_official_url
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_file, save_json


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.tse.jus.br/a",
        "https://evil.example/a",
        "https://cdn.tse.jus.br@evil.example/a",
        "https://cdn.tse.jus.br:123/a",
    ],
)
def test_non_official_download_urls_are_rejected(url):
    with pytest.raises(IngestionError):
        validate_official_url(url)


def test_redirect_cannot_escape_official_hosts(configuration):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "https://evil.example/x"})
    )
    with httpx.Client(transport=transport) as client:
        official = OfficialHttpClient(configuration, client)
        with (
            pytest.raises(IngestionError, match="UNTRUSTED_RESOURCE_URL"),
            official.stream_response("https://cdn.tse.jus.br/a.zip"),
        ):
            pass


def test_304_requires_intact_cached_file(configuration, tmp_path):
    path = tmp_path / "archive.zip"
    path.write_bytes(b"archive")
    timestamp = datetime.now(UTC).isoformat()
    resource = Resource(
        "test", "Candidatos", "https://cdn.tse.jus.br/a.zip", "candidate", 2026, "candidatos-2026"
    )
    save_json(
        configuration.storage_directory / "manifests/test.json",
        {
            "source_url": resource.url,
            "path": str(path),
            "sha256": hash_file(path),
            "bytes": 7,
            "fetched_at": timestamp,
            "last_full_check_at": timestamp,
            "checked_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "etag": '"test"',
        },
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(304))
    with httpx.Client(transport=transport) as client:
        artifact = download_resource(
            resource, configuration, OfficialHttpClient(configuration, client), DownloadBudget()
        )
        assert artifact.sha256 == hash_file(path)
        assert artifact.acquisition_status == "cached"
        path.write_bytes(b"corrupted")
        with pytest.raises(IngestionError, match="INVALID_NOT_MODIFIED_RESPONSE"):
            download_resource(
                resource, configuration, OfficialHttpClient(configuration, client), DownloadBudget()
            )


def test_cognitive_review_flags_deep_nested_control(tmp_path):
    path = tmp_path / "nested.py"
    path.write_text(
        "def calculate_records(records):\n"
        "    for row in records:\n"
        "        if row:\n"
        "            for item in row:\n"
        "                if item:\n"
        "                    while item:\n"
        "                        if item > 2:\n"
        "                            item -= 1\n"
    )
    rules = {finding.rule for finding in review_python_file(path)}
    assert "nesting_depth" in rules
    assert "cognitive_complexity" in rules
