"""Reclaim table bloat with VACUUM FULL. Dry run by default; --apply is explicit.

VACUUM FULL rewrites the table and its indexes under ACCESS EXCLUSIVE, so the table is
unreadable and unwritable until it ends (seconds for person_data_gap, ~92 MB). It needs free
disk of about the size of the rewritten table. Stop collection workers first; a lock_timeout
aborts the run instead of queueing behind a worker and blocking everyone behind it.
"""

import argparse
import re
import sys
from pathlib import Path

from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from service.ingestion.contracts import IngestionError  # noqa: E402

DEFAULT_TABLE = "se_liga_brasil.person_data_gap"
QUALIFIED_TABLE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")
ROW_HEADER_BYTES = 24
BYTES_PER_MEGABYTE = 1024 * 1024


def read_table_footprint(connection, table: str) -> dict:
    return connection.execute(
        """
        SELECT pg_table_size(c.oid) / 1048576.0 AS table_mb,
          pg_indexes_size(c.oid) / 1048576.0 AS index_mb, c.reltuples::bigint AS estimated_rows,
          s.n_live_tup AS live_rows, s.n_dead_tup AS dead_rows, s.n_tup_upd AS updates_total,
          s.last_autovacuum,
          (SELECT sum(avg_width) + %s FROM pg_stats
           WHERE schemaname = s.schemaname AND tablename = s.relname) AS estimated_row_bytes
        FROM pg_class c JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE c.oid = %s::regclass
        """,
        (ROW_HEADER_BYTES, table),
    ).fetchone()


def estimate_reclaimable(footprint: dict) -> dict:
    row_bytes = footprint["estimated_row_bytes"]
    if row_bytes is None or footprint["estimated_rows"] < 0:
        return {**describe_footprint(footprint), "estimated_table_bloat_mb": "unknown (no stats)"}
    expected_mb = footprint["estimated_rows"] * row_bytes / BYTES_PER_MEGABYTE
    return {
        **describe_footprint(footprint),
        "expected_table_mb_without_bloat": round(float(expected_mb), 1),
        "estimated_table_bloat_mb": round(max(float(footprint["table_mb"]) - expected_mb, 0), 1),
    }


def describe_footprint(footprint: dict) -> dict:
    return {
        "table_mb": round(float(footprint["table_mb"]), 1),
        "index_mb": round(float(footprint["index_mb"]), 1),
        "live_rows": footprint["live_rows"],
        "dead_rows": footprint["dead_rows"],
        "updates_total": footprint["updates_total"],
        "last_autovacuum": str(footprint["last_autovacuum"]),
    }


def find_other_sessions_using_table(connection, table: str) -> int:
    return connection.execute(
        """
        SELECT count(DISTINCT l.pid) AS sessions FROM pg_locks l
        WHERE l.relation = %s::regclass AND l.pid <> pg_backend_pid()
        """,
        (table,),
    ).fetchone()["sessions"]


def vacuum_full(connection, table: str, lock_timeout_seconds: int) -> None:
    schema_name, table_name = table.split(".")
    connection.execute(sql.SQL("SET lock_timeout = {}").format(lock_timeout_seconds * 1000))
    connection.execute(
        sql.SQL("VACUUM (FULL, ANALYZE) {}.{}").format(
            sql.Identifier(schema_name), sql.Identifier(table_name)
        )
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--table", default=DEFAULT_TABLE, help="schema.table (default: %(default)s)"
    )
    parser.add_argument("--lock-timeout-seconds", type=int, default=15)
    parser.add_argument(
        "--apply", action="store_true", help="run VACUUM FULL; without it only report (dry run)"
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if not QUALIFIED_TABLE.match(arguments.table):
        raise IngestionError("INVALID_TABLE_NAME")
    with connect_database(arguments.env_file) as connection:
        before = estimate_reclaimable(read_table_footprint(connection, arguments.table))
        sessions = find_other_sessions_using_table(connection, arguments.table)
        print(
            {
                "mode": "apply" if arguments.apply else "dry-run",
                "before": before,
                "other_sessions_holding_locks": sessions,
            }
        )
        if not arguments.apply:
            print("Dry run: nothing changed. Stop workers, then repeat with --apply.")
            return 0
        if sessions:
            print("Aborted: other sessions hold locks on the table; stop workers and retry.")
            return 1
        vacuum_full(connection, arguments.table, arguments.lock_timeout_seconds)
        print({"after": estimate_reclaimable(read_table_footprint(connection, arguments.table))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
