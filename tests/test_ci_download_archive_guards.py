"""Untrusted archive sizes, headers and scalar encodings fail before projection."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zipfile import ZipInfo

import httpx
import pytest

from crawlers.tse import archive_reader
from normalization.scalars import normalize_boolean, normalize_timestamp
from service.acquisition import downloader
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_file


def configuration(tmp_path, **values):
    return SimpleNamespace(
        **(
            {
                "storage_directory": tmp_path,
                "max_download_bytes": 10,
                "max_run_download_bytes": 20,
                "force_recheck_after_hours": 2,
            }
            | values
        )
    )


def resource(suffix=".zip"):
    return Resource(
        "resource",
        "Source",
        "https://cdn.tse.jus.br/source",
        "candidate",
        2024,
        "source",
        file_suffix=suffix,
    )


def test_cached_manifest_validators_expire_and_preserve_http_conditions(tmp_path):
    now = datetime.now(UTC)
    config = configuration(tmp_path)
    manifest = {"last_full_check_at": now.isoformat(), "etag": '"tag"', "last_modified": "date"}
    assert downloader.build_conditional_headers(manifest, config) == {
        "If-None-Match": '"tag"',
        "If-Modified-Since": "date",
    }
    assert (
        downloader.build_conditional_headers(
            manifest | {"last_full_check_at": (now - timedelta(hours=3)).isoformat()}, config
        )
        == {}
    )
    assert downloader.build_conditional_headers({}, config) == {}


def test_compressed_response_ignores_wire_length_and_reports_decoded_bytes(tmp_path):
    response = httpx.Response(
        200, headers={"content-encoding": "identity", "content-length": "3"}, content=b"abc"
    )
    progress = []
    result = downloader.save_download(
        response,
        resource(),
        configuration(tmp_path),
        DownloadBudget(),
        lambda *args: progress.append(args),
    )
    assert progress == [(3, None)]
    assert result["sha256"] == hash_file(__import__("pathlib").Path(result["path"]))


@pytest.mark.parametrize(
    "suffix,error",
    [(".exe", "UNSUPPORTED_ARTIFACT_SUFFIX"), (".zip", "RUN_DOWNLOAD_LIMIT_EXCEEDED")],
)
def test_rejected_download_never_leaves_partial_file(tmp_path, suffix, error):
    config = configuration(tmp_path, max_run_download_bytes=1 if suffix == ".zip" else 20)
    with pytest.raises(IngestionError, match=error):
        downloader.save_download(
            httpx.Response(200, content=b"abc"), resource(suffix), config, DownloadBudget()
        )
    assert not list((tmp_path / "archives").glob("*.part"))


def test_not_modified_requires_intact_cache_and_reports_progress(tmp_path):
    previous = {"bytes": 3}
    progress = []
    response = httpx.Response(304)
    with pytest.raises(IngestionError, match="INVALID_NOT_MODIFIED_RESPONSE"):
        downloader.select_download_manifest(
            response, resource(), configuration(tmp_path), DownloadBudget(), previous, False
        )
    result = downloader.select_download_manifest(
        response,
        resource(),
        configuration(tmp_path),
        DownloadBudget(),
        previous,
        True,
        lambda *args: progress.append(args),
    )
    assert progress == [(3, 3)] and "checked_at" in result


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("file_size", 11, "ARCHIVE_ENTRY_TOO_LARGE"),
        ("external_attr", 0o120000 << 16, "ARCHIVE_SYMLINK_REJECTED"),
        ("flag_bits", 1, "UNSAFE_ARCHIVE_ENTRY"),
    ],
)
def test_zip_metadata_cannot_bypass_safety_limits(field, value, code):
    entry = ZipInfo("file.csv")
    setattr(entry, field, value)
    with pytest.raises(IngestionError, match=code):
        archive_reader.validate_zip_entry(entry, SimpleNamespace(max_entry_bytes=10))


def test_archive_entry_count_and_expansion_are_both_bounded(monkeypatch):
    monkeypatch.setattr(archive_reader, "MAX_ARCHIVE_ENTRIES", 1)
    config = SimpleNamespace(max_archive_expanded_bytes=10)
    with pytest.raises(IngestionError, match="ARCHIVE_ENTRY_LIMIT_EXCEEDED"):
        archive_reader.validate_zip_entries(SimpleNamespace(infolist=lambda: [None, None]), config)
    with pytest.raises(IngestionError, match="ARCHIVE_EXPANSION_LIMIT_EXCEEDED"):
        archive_reader.validate_zip_entries(
            SimpleNamespace(infolist=lambda: [SimpleNamespace(file_size=11)]), config
        )


@pytest.mark.parametrize(
    "headers,code",
    [
        (None, "INVALID_CSV_HEADER"),
        (["A", "A"], "INVALID_CSV_HEADER"),
        (["A"], "CSV_SCHEMA_CHANGED"),
    ],
)
def test_csv_schema_changes_are_reported_before_data_rows(headers, code):
    with pytest.raises(IngestionError, match=code):
        archive_reader.validate_csv_headers(headers, "candidate")


@pytest.mark.parametrize("value", ["invalid", "2024-01-01 0:00:00"])
def test_timestamp_rejects_impossible_or_noncanonical_encodings(value):
    with pytest.raises(IngestionError, match="INVALID_TIMESTAMP"):
        normalize_timestamp(value, time_zone=UTC)
    assert normalize_timestamp(None, time_zone=UTC) is None
    assert normalize_timestamp("2024-01-01 00:00:00", time_zone=UTC).endswith("+00:00")


def test_unrecognized_boolean_does_not_become_truthy():
    with pytest.raises(IngestionError, match="INVALID_BOOLEAN"):
        normalize_boolean("yes")
