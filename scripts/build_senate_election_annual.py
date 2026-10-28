"""Attach sourced election-year party labels without changing annual seat totals."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from database.senate_elections import fetch_election_year_senate_partitions
from service.senate_history.collection import publish_senate_history
from service.senate_history.elections import merge_senate_election_observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    arguments = parser.parse_args()
    source = Path("data/senate-elections/historical-election-observations.json")
    evidence = json.loads(source.read_text())
    if evidence["schema_version"] != "historical_senate_elections.v1":
        raise ValueError("UNSUPPORTED_SENATE_ELECTION_SCHEMA")
    observations = evidence["observations"]
    with connect_database(arguments.env_file) as connection, connection.transaction():
        existing = fetch_election_year_senate_partitions(connection, observations)
        partitions = merge_senate_election_observations(existing, observations)
        entries = publish_senate_history(
            partitions, Path("data/political-dashboard"), AnnualDashboardRepository(connection),
            manifest_name="senate-elections-manifest.json",
        )
    print(json.dumps({"partitions": len(entries), "election_observations": len(observations)}))


if __name__ == "__main__":
    main()
