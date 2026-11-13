"""Archive database tables to local NDJSON.gz files, verify them against the database, restore.

export  reads the database only (read-only, single REPEATABLE READ snapshot, server-side cursor).
verify  re-reads the files and compares counts and hashes with the database (read-only).
restore writes: --dry-run runs everything in a transaction that is rolled back.
plan    lists the tables with their size (read-only).
See docs/arquivamento-ingestao.md.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import PROJECT_ROOT, connect_database  # noqa: E402
from service.archive_export.catalog import list_tables  # noqa: E402
from service.archive_export.contracts import ArchiveError  # noqa: E402
from service.archive_export.exporter import export_archive  # noqa: E402
from service.archive_export.manifest import (  # noqa: E402
    manifest_sha256,
    utc_timestamp_directory_name,
    write_verification_receipt,
)
from service.archive_export.restorer import MODES, restore_archive  # noqa: E402
from service.archive_export.targets import MAIN_SCHEMA, SCOPES, select_targets  # noqa: E402
from service.archive_export.verifier import verify_archive  # noqa: E402

DEFAULT_ARCHIVE_ROOT = PROJECT_ROOT / "data" / "database_snapshot"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", type=Path, default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--scope", choices=SCOPES, default="snapshot")
    export.add_argument("--output-dir", type=Path, default=None)
    export.add_argument("--table", action="append", default=[])
    verify = commands.add_parser("verify")
    verify.add_argument("--archive-dir", type=Path, required=True)
    verify.add_argument("--table", action="append", default=[])
    restore = commands.add_parser("restore")
    restore.add_argument("--archive-dir", type=Path, required=True)
    restore.add_argument("--table", action="append", default=[])
    restore.add_argument("--mode", choices=MODES, default="insert")
    restore.add_argument("--column", action="append", default=[])
    restore.add_argument("--dry-run", action="store_true")
    commands.add_parser("plan")
    return parser


def run_export(connection, options) -> int:
    directory = options.output_dir or DEFAULT_ARCHIVE_ROOT / utc_timestamp_directory_name()
    targets = select_targets(connection, options.scope, options.table)
    result = export_archive(
        connection, targets, directory, options.scope, lambda text: print(text, file=sys.stderr)
    )
    total = sum(entry["file_bytes"] for entry in result["files"])
    print(
        json.dumps(
            {
                "directory": result["directory"],
                "files": len(result["files"]),
                "total_compressed_bytes": total,
            },
            indent=2,
        )
    )
    print("Next: verify --archive-dir " + result["directory"], file=sys.stderr)
    return 0


def run_verify(connection, options) -> int:
    report = verify_archive(connection, options.archive_dir, options.table or None)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["all_files_ok"] and not options.table:
        write_verification_receipt(options.archive_dir, report)
        print("VERIFIED manifest_sha256=" + manifest_sha256(options.archive_dir), file=sys.stderr)
    return 0 if report["all_files_ok"] else 1


def run_restore(connection, options) -> int:
    results = restore_archive(
        connection,
        options.archive_dir,
        options.table or None,
        options.mode,
        options.column or None,
        options.dry_run,
    )
    print(json.dumps(results, indent=2))
    return 0


def run_plan(connection, _options) -> int:
    rows = list_tables(connection, MAIN_SCHEMA)
    print(json.dumps({"tables": rows}, indent=2, default=str))
    return 0


def main() -> int:
    options = build_parser().parse_args()
    handlers = {
        "export": run_export,
        "verify": run_verify,
        "restore": run_restore,
        "plan": run_plan,
    }
    try:
        with connect_database(options.env_file) as connection:
            return handlers[options.command](connection, options)
    except ArchiveError as error:
        print(f"ARCHIVE_ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
