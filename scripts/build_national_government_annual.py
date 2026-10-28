"""Publish dated national observations while preserving richer existing UF evidence."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import AnnualDashboardRepository  # noqa: E402
from service.political_dashboard.contracts import STATE_NAMES  # noqa: E402
from service.political_dashboard_dataset.executive import (  # noqa: E402
    build_annual_executive_partitions,
    documented_exercise_year_bounds,
)
from service.political_dashboard_dataset.executive_observations import (  # noqa: E402
    merge_executive_observations,
)
from service.political_dashboard_dataset.storage import store_partition  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("data/national-government-history/historical-executive-evidence.json"),
    )
    parser.add_argument("--storage", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--uf", nargs="+", choices=STATE_NAMES)
    parser.add_argument("--year", type=int)
    arguments = parser.parse_args()
    evidence = json.loads(arguments.evidence.read_text())
    if evidence.get("schema_version") != "national_government_observations.v1":
        raise ValueError("UNSUPPORTED_EXECUTIVE_EVIDENCE_SCHEMA")
    selected = [
        row
        for row in evidence["exercises"]
        if not arguments.uf or row["territory_code"] in arguments.uf
    ]
    first, last = documented_exercise_year_bounds({**evidence, "exercises": selected})
    if arguments.year is not None:
        first = last = arguments.year
    partitions = []
    with connect_database(arguments.env_file) as connection:
        repository = AnnualDashboardRepository(connection)
        for year in range(first, last + 1):
            incoming = build_annual_executive_partitions(selected, year, date.today())
            if not incoming:
                continue
            territories = list({row["territory_code"] for row in incoming})
            old = {
                (row["payload"]["territory_code"], row["payload"]["institution_code"]): row[
                    "payload"
                ]
                for row in repository.fetch_government_partitions(year, territories)
            }
            partitions.extend(
                merge_executive_observations(
                    old.get((row["territory_code"], row["institution_code"])), row
                )
                for row in incoming
            )
        if arguments.activate:
            with connection.transaction():
                repository.activate_partitions(partitions)
                repository.remove_replaced_invalid_district_government()
    entries = [store_partition(arguments.storage, row) for row in partitions]
    print(
        json.dumps(
            {
                "partitions": len(entries),
                "source_observations": len(evidence["exercises"]),
                "selected_observations": len(selected),
                "activated": arguments.activate,
            }
        )
    )


if __name__ == "__main__":
    main()
