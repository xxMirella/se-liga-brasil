import zipfile
from dataclasses import replace

import pytest

from crawlers.tse.validator import validate_resource
from service.ingestion.contracts import IngestionError
from storage.files import hash_file, read_json_lines
from storage.validation_index import ValidationIndex


def test_valid_rows_are_normalized_and_invalid_rows_quarantined(
    configuration, archive_factory, candidate_row
):
    rows = [candidate_row, candidate_row | {"SQ_CANDIDATO": "2", "DT_NASCIMENTO": "31/02/2000"}]
    artifact = archive_factory("candidate", rows)
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        validated = validate_resource(artifact, configuration, index)
        assert validated.summary["valid"] == 1
        assert validated.summary["rejected"] == 1
        assert list(read_json_lines(validated.rejected_path))[0]["reasonCode"] == "INVALID_DATE"
        assert (
            list(read_json_lines(validated.records_path))[0]["normalizedData"]["civilName"]
            == "Pessoa Fictícia"
        )
    finally:
        index.close()


def test_missing_headers_fail_entire_archive(configuration, archive_factory, candidate_row):
    del candidate_row["CD_CARGO"]
    artifact = archive_factory("candidate", [candidate_row])
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        with pytest.raises(IngestionError, match="CSV_SCHEMA_CHANGED"):
            validate_resource(artifact, configuration, index)
    finally:
        index.close()


def test_conflicting_duplicate_does_not_publish_staging(
    configuration, archive_factory, candidate_row
):
    artifact = archive_factory(
        "candidate", [candidate_row, candidate_row | {"NM_CANDIDATO": "Outro"}]
    )
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        with pytest.raises(IngestionError, match="CONFLICTING_DUPLICATE_KEY"):
            validate_resource(artifact, configuration, index)
        assert not list(configuration.storage_directory.rglob("records.ndjson"))
    finally:
        index.close()


def test_zip_path_traversal_is_rejected(configuration, archive_factory, candidate_row):
    artifact = archive_factory("candidate", [candidate_row], entry_name="../evil.csv")
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        with pytest.raises(IngestionError, match="UNSAFE_ARCHIVE_ENTRY"):
            validate_resource(artifact, configuration, index)
    finally:
        index.close()


def test_documents_are_opaque_and_match_official_filename(
    configuration, archive_factory, candidate_row
):
    artifact = archive_factory("criminal_certificate", [candidate_row])
    with zipfile.ZipFile(artifact.path, "w") as archive:
        archive.writestr("PA/2026PA10000000001_123.pdf.pdf", b"%PDF-1.4\nsynthetic opaque evidence")
    artifact = replace(artifact, sha256=hash_file(artifact.path))
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        validated = validate_resource(artifact, configuration, index)
        record = list(read_json_lines(validated.records_path))[0]
        assert record["normalizedData"]["candidateSequence"] == "10000000001"
        assert "conviction" not in str(record)
    finally:
        index.close()
