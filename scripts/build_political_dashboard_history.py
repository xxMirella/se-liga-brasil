"""Build the per-territory dashboard history from the published annual partitions.

Default is a dry run: it only reads, reports what would be written and writes nothing.
`--apply` (explicit) creates the table if needed and upserts changed territories in a single
transaction. Run it once to backfill; afterwards every annual publication refreshes the
histories of the territories it touches.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database, read_sql_file  # noqa: E402
from database.political_dashboard_analytical import AnnualDashboardRepository  # noqa: E402
from database.political_dashboard_history import DashboardHistoryTable  # noqa: E402

MIGRATION = "political_dashboard_history.sql"


def describe_entries(entries, current_digests):
    return [
        {
            "territory_code": entry["territory_code"], "rows": entry["row_count"],
            "uncompressed_bytes": entry["uncompressed_bytes"],
            "compressed_bytes": len(entry["payload_zlib"]),
            "status": (
                "new" if entry["territory_code"] not in current_digests
                else "unchanged" if current_digests[entry["territory_code"]]
                == entry["content_sha256"] else "changed"
            ),
        }
        for entry in entries
    ]


def plan(connection, requested):
    table = DashboardHistoryTable(connection)
    territories = requested or table.list_annual_territories()
    entries = AnnualDashboardRepository(connection).build_history_entries(territories)
    table_exists = table.is_available()
    digests = table.fetch_digests(territories) if table_exists else {}
    return entries, table_exists, digests


def run_dry(connection, requested):
    connection.execute("SET default_transaction_read_only = on")
    with connection.transaction():
        return plan(connection, requested)


def run_apply(connection, requested):
    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('se_liga_brasil:dashboard_history'))"
        )
        table_existed = DashboardHistoryTable(connection).is_available()
        connection.execute(read_sql_file(MIGRATION))
        entries, _, digests = plan(connection, requested)
        changed = DashboardHistoryTable(connection).upsert(entries)
    return entries, table_existed, digests, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--territory", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    arguments = parser.parse_args()
    started = time.perf_counter()
    with connect_database(arguments.env_file) as connection:
        if arguments.apply:
            entries, table_exists, digests, changed = run_apply(connection, arguments.territory)
        else:
            entries, table_exists, digests = run_dry(connection, arguments.territory)
            changed = 0
    print(json.dumps({
        "mode": "apply" if arguments.apply else "dry-run (nothing written)",
        "table_existed": table_exists, "territories_changed_in_database": changed,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "territories": describe_entries(entries, digests),
        "total_compressed_bytes": sum(len(e["payload_zlib"]) for e in entries),
    }, indent=1))


if __name__ == "__main__":
    main()
