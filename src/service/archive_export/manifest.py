"""Manifest of an archive directory: what was exported, from which schema, with which hashes."""

import json
from datetime import UTC, datetime
from pathlib import Path

from service.archive_export.contracts import (
    ARCHIVE_FORMAT_VERSION,
    MANIFEST_FILE_NAME,
    VERIFICATION_FILE_NAME,
    ArchiveError,
)
from storage.files import hash_file

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[3] / "db" / "migrations"


def utc_timestamp_directory_name(moment: datetime | None = None) -> str:
    return (moment or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")


def repository_migration_head() -> str | None:
    """Last migration file of the repository (informational: it may not be applied yet)."""
    names = sorted(path.name for path in MIGRATIONS_DIRECTORY.glob("*.sql"))
    return names[-1] if names else None


def write_manifest(directory: Path, manifest: dict) -> Path:
    path = directory / MANIFEST_FILE_NAME
    temporary = path.with_suffix(".json.partial")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
    return path


def read_manifest(directory: Path) -> dict:
    path = directory / MANIFEST_FILE_NAME
    if not path.is_file():
        raise ArchiveError("MANIFEST_NOT_FOUND")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("archive_format_version") != ARCHIVE_FORMAT_VERSION:
        raise ArchiveError("UNSUPPORTED_ARCHIVE_FORMAT_VERSION")
    return manifest


def manifest_sha256(directory: Path) -> str:
    return hash_file(directory / MANIFEST_FILE_NAME)


def write_verification_receipt(directory: Path, report: dict) -> Path:
    receipt = {
        "verified_at": datetime.now(UTC).isoformat(),
        "manifest_sha256": manifest_sha256(directory),
        "all_files_ok": report["all_files_ok"],
        "files_checked": len(report["files"]),
    }
    path = directory / VERIFICATION_FILE_NAME
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def new_manifest(connection_facts: dict, files: list[dict], scope: str) -> dict:
    return {
        "archive_format_version": ARCHIVE_FORMAT_VERSION,
        "scope": scope,
        "created_at": datetime.now(UTC).isoformat(),
        "row_format": "ndjson.gz: one JSON line per row, row text = to_jsonb(row)::text",
        "repository_migration_head": repository_migration_head(),
        **connection_facts,
        "files": files,
    }


def select_entries(manifest: dict, tables: list[str] | None) -> list[dict]:
    """Entries named by table, `table@slice`, `schema.table[@slice]` or the file name."""
    if not tables:
        return manifest["files"]
    wanted = set(tables)
    return [entry for entry in manifest["files"] if wanted & entry_names(entry)]


def entry_names(entry: dict) -> set[str]:
    slice_suffix = f"@{entry['slice']}" if entry["slice"] else ""
    short = f"{entry['table']}{slice_suffix}"
    return {entry["file"], short, f"{entry['schema']}.{short}"} | (
        set() if entry["slice"] else {entry["table"]}
    )
