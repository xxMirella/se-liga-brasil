"""Re-read an archive and compare it with the database: counts, hashes and source_record hashes."""

import gzip
import hashlib
import json
from itertools import zip_longest
from pathlib import Path

from service.archive_export.catalog import describe_table
from service.archive_export.contracts import ArchiveError, ArchiveTarget
from service.archive_export.manifest import read_manifest, select_entries
from service.archive_export.row_format import ArchivedRow, decode_line, hash_row_text
from service.archive_export.selection import ROW_DIGEST_EXPRESSION, build_ordered_select
from service.archive_export.snapshot_connection import read_only_snapshot, stream_rows
from storage.files import hash_content, hash_file

DIFFERENCE_SAMPLE_SIZE = 5


def iter_archived_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="\n") as stream:
        for line in stream:
            yield decode_line(line)


def payload_hash_matches(row: ArchivedRow) -> bool:
    record = json.loads(row.row_text)
    if record.get("payload") is None:
        return True
    return hash_content(record["payload"]) == record["content_sha256"]


def scan_rows(path: Path, verify_payload_hash: bool) -> dict:
    digest, count, corrupted, payload_mismatches = hashlib.sha256(), 0, 0, 0
    for row in iter_archived_rows(path):
        count += 1
        digest.update(row.row_sha256.encode("ascii"))
        corrupted += hash_row_text(row.row_text) != row.row_sha256
        if verify_payload_hash:
            payload_mismatches += not payload_hash_matches(row)
    return {
        "row_count_scanned": count,
        "row_hashes_sha256_scanned": digest.hexdigest(),
        "corrupted_rows": corrupted,
        "payload_content_sha256_mismatches": payload_mismatches,
    }


def inspect_file(directory: Path, entry: dict) -> dict:
    """Check the file alone: sha256, size, row count, each row hash and the aggregate hash."""
    path = directory / entry["file"]
    if not path.is_file():
        return {"file_present": False, "file_ok": False}
    checks = {
        "file_present": True,
        "file_sha256_ok": hash_file(path) == entry["file_sha256"],
        "file_bytes_ok": path.stat().st_size == entry["file_bytes"],
    }
    if not (checks["file_sha256_ok"] and checks["file_bytes_ok"]):
        return {**checks, "file_ok": False}
    try:
        scan = scan_rows(path, entry["verify_source_record_payload_hash"])
    except (EOFError, OSError, ValueError, ArchiveError) as error:
        return {**checks, "file_ok": False, "unreadable": str(error)}
    checks["row_count_ok"] = scan["row_count_scanned"] == entry["row_count"]
    checks["row_hashes_digest_ok"] = scan["row_hashes_sha256_scanned"] == entry["row_hashes_sha256"]
    checks["corrupted_rows"] = scan["corrupted_rows"]
    checks["payload_content_sha256_mismatches"] = scan["payload_content_sha256_mismatches"]
    checks["file_ok"] = (
        checks["row_count_ok"]
        and checks["row_hashes_digest_ok"]
        and not scan["corrupted_rows"]
        and not scan["payload_content_sha256_mismatches"]
    )
    return checks


def compare_with_database(connection, directory: Path, entry: dict, index: int) -> dict:
    """Walk file and database in the same primary-key order and compare key and row hash."""
    target = ArchiveTarget(entry["schema"], entry["table"], entry["slice"], entry["filter_sql"])
    with read_only_snapshot(connection):
        description = describe_table(connection, target.schema, target.table)
        query = build_ordered_select(target, description, ROW_DIGEST_EXPRESSION)
        database_rows = stream_rows(connection, query, f"archive_verify_{index}")
        file_rows = iter_archived_rows(directory / entry["file"])
        return count_differences(file_rows, database_rows)


def count_differences(file_rows, database_rows) -> dict:
    file_count = database_count = differing = 0
    samples: list[str] = []
    for archived, stored in zip_longest(file_rows, database_rows):
        file_count += archived is not None
        database_count += stored is not None
        if archived is None or stored is None or (archived.key_text, archived.row_sha256) != stored:
            differing += 1
            if len(samples) < DIFFERENCE_SAMPLE_SIZE:
                samples.append(archived.key_text if archived is not None else stored[0])
    return {
        "database_row_count": database_count,
        "archive_row_count": file_count,
        "rows_differing_from_database": differing,
        "differing_key_samples": samples,
        "database_matches": differing == 0,
    }


def verify_archive(connection, directory: Path, tables: list[str] | None = None) -> dict:
    manifest = read_manifest(directory)
    entries = select_entries(manifest, tables)
    if not entries:
        raise ArchiveError("NO_ARCHIVED_FILE_MATCHES_TABLE_FILTER")
    reports = []
    for index, entry in enumerate(entries):
        report = {"file": entry["file"], **inspect_file(directory, entry)}
        if report["file_ok"]:
            report.update(compare_with_database(connection, directory, entry, index))
        reports.append(report)
    return {
        "files": reports,
        "all_files_ok": all(r["file_ok"] and r.get("database_matches") for r in reports),
    }
