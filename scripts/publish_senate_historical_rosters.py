"""Attach official older rolls while retaining any existing exact annual snapshots."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from database.senate_history import (
    fetch_existing_senate_partitions,
    fetch_verified_senator_identities,
)
from service.senate_history.collection import associate_verified_senators, publish_senate_history
from service.senate_history.rosters import attach_historical_rosters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    options = parser.parse_args()
    source = Path("data/senate-history/historical-legislature-rosters.json")
    rosters = json.loads(source.read_text())["rosters"]
    with connect_database(options.env_file) as connection:
        existing = fetch_existing_senate_partitions(connection, 1826, 1991)
        partitions = attach_historical_rosters(existing, rosters, 1826, 1991)
        associate_verified_senators(partitions, fetch_verified_senator_identities(connection))
        entries = publish_senate_history(
            partitions, Path("data/political-dashboard"), AnnualDashboardRepository(connection),
            manifest_name="senate-rosters-manifest.json",
        )
    print(json.dumps({"partitions": len(entries), "roster_records": len(rosters),
                      "first_year": min(row["year"] for row in partitions),
                      "last_year": max(row["year"] for row in partitions)}))


if __name__ == "__main__":
    main()
