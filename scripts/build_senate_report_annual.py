"""Validate archived official dated compositions and publish only complete aggregate snapshots."""

import argparse
import json
from pathlib import Path

from crawlers.senado.annual_reports import extract_annual_report_text
from crawlers.senado.paired_annual_composition import parse_report_senate_composition
from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from service.senate_history.collection import publish_senate_history
from service.senate_history.report_compositions import merge_dated_report_composition
from storage.files import hash_file, save_json


def validate_report_archives(directory):
    validated, rejected = [], []
    for source in sorted(directory.glob("*-evidence.json")):
        evidence = json.loads(source.read_text())
        archive = directory / "archives" / (evidence["sha256"] + ".pdf")
        if hash_file(archive) != evidence["sha256"]:
            raise ValueError("SENATE_REPORT_ARCHIVE_HASH_MISMATCH")
        content = extract_annual_report_text(archive)
        try:
            validated.append(parse_report_senate_composition(content, evidence["year"], evidence))
        except ValueError as error:
            rejected.append({"year": evidence["year"], "reason": str(error),
                             "url": evidence["url"]})
    return validated, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    options = parser.parse_args()
    directory = Path("data/senate-annual-reports")
    compositions, rejected = validate_report_archives(directory)
    partitions = []
    with connect_database(options.env_file) as connection, connection.transaction():
        rows = connection.execute(
            "SELECT year,payload FROM se_liga_brasil.political_dashboard_annual "
            "WHERE institution_code='senado' AND territory_code='BR' AND year=ANY(%s) "
            "ORDER BY year FOR UPDATE", ([row["year"] for row in compositions],),
        ).fetchall()
        existing = {row["year"]: row["payload"] for row in rows}
        partitions = [merge_dated_report_composition(existing.get(row["year"]), row)
                      for row in compositions]
        entries = publish_senate_history(
            partitions, Path("data/political-dashboard"), AnnualDashboardRepository(connection),
            manifest_name="senate-reports-manifest.json",
        )
    save_json(directory / "validated-compositions.json", {
        "schema_version": "senate_dated_aggregate_compositions.v1",
        "compositions": compositions, "errors": rejected,
    })
    print(json.dumps({"partitions": len(entries), "accepted_years": [
        row["year"] for row in compositions], "rejected": rejected}))


if __name__ == "__main__":
    main()
