"""Streaming export of tables to NDJSON.gz inside one read-only snapshot."""

import gzip
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from service.archive_export.catalog import describe_table, schema_fingerprint
from service.archive_export.contracts import ArchiveError, ArchiveTarget
from service.archive_export.manifest import new_manifest, write_manifest
from service.archive_export.row_format import encode_line
from service.archive_export.selection import ROW_TEXT_EXPRESSION, build_ordered_select
from service.archive_export.snapshot_connection import read_only_snapshot, stream_rows
from storage.files import hash_file

COMPRESSION_LEVEL = 6


def write_rows_gzip(path: Path, rows) -> tuple[int, str]:
    """Write (key_text, row_text) rows; return the row count and the digest of all row hashes."""
    digest = hashlib.sha256()
    count = 0
    with (
        path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=COMPRESSION_LEVEL) as stream,
    ):
        for key_text, row_text in rows:
            row_hash, line = encode_line(key_text, row_text)
            stream.write(line)
            digest.update(row_hash.encode("ascii"))
            count += 1
    return count, digest.hexdigest()


def export_target(connection, target: ArchiveTarget, directory: Path, index: int) -> dict:
    description = describe_table(connection, target.schema, target.table)
    query = build_ordered_select(target, description, ROW_TEXT_EXPRESSION)
    final_path = directory / target.file_name
    partial_path = final_path.with_suffix(".gz.partial")
    started = datetime.now(UTC)
    rows = stream_rows(connection, query, f"archive_export_{index}")
    row_count, hashes_digest = write_rows_gzip(partial_path, rows)
    partial_path.replace(final_path)
    return {
        "file": target.file_name,
        "schema": target.schema,
        "table": target.table,
        "slice": target.slice_name,
        "filter_sql": target.slice_predicate_sql,
        "columns": list(description.columns),
        "primary_key": list(description.primary_key),
        "identity_columns": list(description.identity_columns),
        "row_count": row_count,
        "file_bytes": final_path.stat().st_size,
        "file_sha256": hash_file(final_path),
        "row_hashes_sha256": hashes_digest,
        "verify_source_record_payload_hash": target.verify_source_record_payload_hash,
        "exported_at": started.isoformat(),
    }


def describe_connection(connection, schema: str) -> dict:
    version = connection.execute("SHOW server_version").fetchone()
    version_text = list(version.values() if isinstance(version, dict) else version)[0]
    return {
        "database_server_version": version_text,
        "schema": schema,
        "schema_fingerprint_sha256": schema_fingerprint(connection, schema),
        "snapshot_isolation": "REPEATABLE READ, read only",
    }


def export_archive(
    connection,
    targets: list[ArchiveTarget],
    directory: Path,
    scope: str,
    progress: Callable[[str], None] = lambda message: None,
) -> dict:
    """Export every target from one consistent snapshot; the manifest is written last."""
    if directory.exists() and any(directory.iterdir()):
        raise ArchiveError("ARCHIVE_DIRECTORY_NOT_EMPTY")
    directory.mkdir(parents=True, exist_ok=True)
    with read_only_snapshot(connection):
        facts = describe_connection(connection, targets[0].schema)
        files = []
        for index, target in enumerate(targets):
            entry = export_target(connection, target, directory, index)
            files.append(entry)
            progress(f"{entry['file']}: {entry['row_count']} rows, {entry['file_bytes']} bytes")
    write_manifest(directory, new_manifest(facts, files, scope))
    return {"directory": str(directory), "files": files}
