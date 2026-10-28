"""Rebuild the complete yearly Senate history from archived, normalized evidence only."""

import argparse
import json
from datetime import date
from pathlib import Path

from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from database.senate_history import fetch_verified_senator_identities
from service.senate_history.collection import (
    associate_verified_senators,
    build_senate_history_partitions,
    publish_senate_history,
)
from service.senate_history.elections import attach_senate_elections
from service.senate_history.institutional_context import attach_senate_institutional_context
from service.senate_history.report_compositions import attach_dated_report_compositions
from service.senate_history.rosters import attach_historical_rosters
from storage.files import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    options = parser.parse_args()
    directory = Path("data/senate-history")
    evidence = json.loads((directory / "historical-senate-evidence.json").read_text())
    rosters = json.loads((directory / "historical-legislature-rosters.json").read_text())
    if evidence["schema_version"] != "historical_senate_evidence.v1" or (
        rosters["schema_version"] != "historical_senate_rosters.v1"
    ):
        raise ValueError("UNSUPPORTED_SENATE_HISTORY_EVIDENCE_SCHEMA")
    partitions = build_senate_history_partitions(
        evidence["exercises"], evidence["affiliations"], 1826, date.today().year - 1,
    )
    partitions = attach_historical_rosters(
        partitions, rosters["rosters"], 1826, date.today().year - 1,
    )
    partitions = attach_senate_institutional_context(partitions)
    election_source = Path("data/senate-elections/historical-election-observations.json")
    if election_source.exists():
        election_evidence = json.loads(election_source.read_text())
        if election_evidence["schema_version"] != "historical_senate_elections.v1":
            raise ValueError("UNSUPPORTED_SENATE_ELECTION_SCHEMA")
        partitions = attach_senate_elections(partitions, election_evidence["observations"])
    report_source = Path("data/senate-annual-reports/validated-compositions.json")
    if report_source.exists():
        report_evidence = json.loads(report_source.read_text())
        if report_evidence["schema_version"] != "senate_dated_aggregate_compositions.v1":
            raise ValueError("UNSUPPORTED_SENATE_REPORT_SCHEMA")
        partitions = attach_dated_report_compositions(partitions, report_evidence["compositions"])
    with connect_database(options.env_file) as connection:
        associated = associate_verified_senators(
            partitions, fetch_verified_senator_identities(connection),
        )
        entries = publish_senate_history(
            partitions, Path("data/political-dashboard"), AnnualDashboardRepository(connection),
        )
    audit = {
        "partitions": len(entries), "linked_source_people": associated,
        "exercises": len(evidence["exercises"]), "source_people": len(evidence["affiliations"]),
        "legislature_roster_records": len(rosters["rosters"]),
        "national_years": [{"year": row["year"], "simultaneous_observed_people": row["total"],
                            "legislature_records": len(row.get("historical_roster", [])),
                            "political_parties": row["political_parties"]}
                           for row in partitions if row["territory_code"] == "BR"],
    }
    save_json(directory / "annual-publication-audit.json", audit)
    print(json.dumps({key: value for key, value in audit.items() if key != "national_years"}))


if __name__ == "__main__":
    main()
