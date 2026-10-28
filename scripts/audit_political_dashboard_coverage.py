"""Audit published annual projections without confusing coverage with complete history."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from storage.files import save_json

COVERAGE_QUERY = """
SELECT institution_code,territory_code,min(year) AS first_year,max(year) AS last_year,
 count(*) AS published_years,
 count(*) FILTER(WHERE payload->>'snapshot_on' IS NOT NULL) AS years_with_dated_snapshot,
 count(*) FILTER(WHERE payload->>'coverage'='legislature_roster_only') AS roster_only_years,
 max(published_at)::text AS latest_publication
FROM se_liga_brasil.political_dashboard_annual
GROUP BY institution_code,territory_code ORDER BY institution_code,territory_code
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path("data/political-dashboard/coverage-audit.json"))
    options = parser.parse_args()
    with connect_database(options.env_file) as connection:
        coverage = connection.execute(COVERAGE_QUERY).fetchall()
        current = connection.execute(
            "SELECT year,territory_code,institution_code,payload->>'total' AS observed_people, "
            "payload->>'snapshot_on' AS snapshot_on FROM se_liga_brasil.political_dashboard_annual "
            "WHERE year=(SELECT max(year) FROM se_liga_brasil.political_dashboard_annual) "
            "AND territory_code='BR' ORDER BY institution_code"
        ).fetchall()
    result = {
        "schema_version": "political_dashboard_coverage_audit.v1", "coverage": coverage,
        "current_national_partitions": current,
        "semantics": "Published years may be partial; roster records are not simultaneous seats",
    }
    save_json(options.output, result)
    print(json.dumps({"scopes": len(coverage), "published_annual_partitions": sum(
        row["published_years"] for row in coverage
    ), "current_national_partitions": current}, ensure_ascii=False))


if __name__ == "__main__":
    main()
