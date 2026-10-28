"""Audit current territorial scopes without assuming their historical existence."""

import argparse
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from database.operations import connect_database
from service.coverage_audit.annual import (
    annual_scope_coverage,
    partition_metrics,
    summarize_scopes,
)
from storage.files import save_json


def collect_published_metrics(connection):
    canonical_ids = {str(row["id"]) for row in connection.execute(
        "SELECT id FROM se_liga_brasil.person",
    ).fetchall()}
    rows, sizes = [], []
    with connection.cursor(name="annual_coverage_audit") as cursor:
        cursor.itersize = 500
        cursor.execute("SELECT payload,octet_length(payload::text) bytes "
                       "FROM se_liga_brasil.political_dashboard_annual "
                       "ORDER BY year,territory_code,institution_code")
        for record in cursor:
            rows.append(partition_metrics(record["payload"], canonical_ids))
            sizes.append(record["bytes"])
    return rows, sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--start-year", type=int, default=1880)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--output", type=Path,
                        default=Path("data/political-dashboard/annual-coverage-audit-20261027.json"))
    options = parser.parse_args()
    catalog = json.loads(Path("data/ibge-territories/territories.json").read_text())
    with connect_database(options.env_file) as connection, connection.transaction():
        rows, sizes = collect_published_metrics(connection)
    scopes, uncatalogued = annual_scope_coverage(
        rows, catalog, options.start_year, options.end_year,
    )
    report = {"schema_version": "annual_timeline_coverage_audit.v1",
              "created_at": datetime.now(UTC).isoformat(),
              "year_start": options.start_year, "year_end": options.end_year,
              "catalog_municipalities": len(catalog["municipalities"]),
              "territorial_semantics": "Current IBGE inventory; absent historical years do not "
                                       "assert territorial or institutional existence then. "
                                       "No record is not proof of no government or representation.",
              "summary": summarize_scopes(scopes),
              "published_partitions": len(rows), "scopes": scopes,
              "published_metrics": rows, "uncatalogued_partitions": uncatalogued,
              "status_counts": dict(Counter(row["status"] for row in rows)),
              "performance": {"uncompressed_partition_bytes_sum": sum(sizes),
                              "maximum_uncompressed_partition_bytes": max(sizes, default=0)}}
    save_json(options.output, report)
    print(json.dumps({key: report[key] for key in (
        "published_partitions", "catalog_municipalities", "status_counts", "performance",
    )}))


if __name__ == "__main__":
    main()
