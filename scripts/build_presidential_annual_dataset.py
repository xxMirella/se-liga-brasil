"""Aggregate verified historical executive evidence by year without inventing party affiliations."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import (
    AnnualDashboardRepository,
    serialize_manifest,
)  # noqa: E402
from service.political_dashboard_dataset.executive import (  # noqa: E402
    build_annual_executive_partitions,
    documented_exercise_year_bounds,
)
from service.political_dashboard_dataset.storage import store_partition, write_atomic  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--activate", action="store_true")
    arguments = parser.parse_args()
    evidence = json.loads(arguments.evidence.read_text())
    if evidence.get("schema_version") != "historical_executive_evidence.v1":
        raise ValueError("UNSUPPORTED_EXECUTIVE_EVIDENCE_SCHEMA")
    exercises = evidence["exercises"]
    start_year, end_year = documented_exercise_year_bounds(evidence)
    years = range(start_year, end_year + 1)
    partitions = [
        partition
        for year in years
        for partition in build_annual_executive_partitions(exercises, year, date.today())
    ]
    entries = [store_partition(arguments.storage, partition) for partition in partitions]
    if arguments.activate:
        with connect_database(arguments.env_file) as connection:
            migration = Path(__file__).resolve().parents[1] / "db/political_dashboard_annual.sql"
            connection.execute(migration.read_text())
            AnnualDashboardRepository(connection).activate_partitions(partitions)
    institution_codes = {exercise["institution_code"] for exercise in exercises}
    manifest_name = {
        frozenset({"presidency"}): "presidency-manifest.json",
        frozenset({"state_government"}): "state-government-manifest.json",
        frozenset({"municipal_government"}): "municipal-government-manifest.json",
    }.get(frozenset(institution_codes), "executive-manifest.json")
    write_atomic(arguments.storage / manifest_name, serialize_manifest(entries).encode())
    print(
        json.dumps(
            {
                "partitions": len(entries),
                "source_exercises": len(exercises),
                "total_bytes": sum(entry["bytes"] for entry in entries),
                "activated": arguments.activate,
            }
        )
    )


if __name__ == "__main__":
    main()
