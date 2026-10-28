"""Publish explicitly partial year-end histories for all verified current-roster people."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.camara.cached_roster import load_cached_current_roster  # noqa: E402
from crawlers.camara.history_archives import (  # noqa: E402
    read_verified_archive,
    read_verified_history,
)
from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import (  # noqa: E402
    AnnualDashboardRepository,
    serialize_manifest,
)
from service.political_dashboard_dataset.camara_history import (  # noqa: E402
    current_cohort_historical_partitions,
)
from service.political_dashboard_dataset.storage import store_partition, write_atomic  # noqa: E402


def load_validated_cohort(storage):
    roster, _ = load_cached_current_roster(storage)
    identifiers = {str(row["id"]) for row in roster}
    histories = [read_verified_history(storage, identifier) for identifier in sorted(identifiers)]
    if not identifiers or {row["official_deputy_id"] for row in histories} != identifiers:
        raise ValueError("INCOMPLETE_CAMARA_HISTORICAL_COHORT")
    legislatures = {}
    required = {
        event["idLegislatura"]
        for row in histories
        for event in row["events"]
        if event["idLegislatura"] >= 51
    }
    for identifier in required:
        archive = json.loads((storage / "camara-legislatures" / f"{identifier}.json").read_text())
        document = read_verified_archive(storage, archive)
        if document != archive["document"]:
            raise ValueError("CAMARA_PREPARED_LEGISLATURE_DIFFERS_FROM_ARCHIVE")
        legislatures[identifier] = document["dados"]
    return histories, legislatures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--storage", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--activate", action="store_true")
    arguments = parser.parse_args()
    histories, legislatures = load_validated_cohort(arguments.source_storage)
    with connect_database(arguments.env_file) as connection:
        repository = AnnualDashboardRepository(connection)
        identities = repository.fetch_verified_camara_identities()
        partitions = [
            partition
            for year in range(2000, 2026)
            for partition in current_cohort_historical_partitions(
                histories, legislatures, identities, year
            )
        ]
        entries = [store_partition(arguments.storage, partition) for partition in partitions]
        if arguments.activate:
            allowed = "current_roster_only_not_all_historical_deputies"
            if any(
                row["annual_cohort"] != allowed
                for row in repository.existing_camara_historical_cohorts()
            ):
                raise ValueError("BROADER_CAMARA_HISTORICAL_DATASET_MUST_BE_PRESERVED")
            repository.activate_partitions(partitions)
    write_atomic(
        arguments.storage / "camara-history-manifest.json", serialize_manifest(entries).encode()
    )
    print(
        json.dumps(
            {
                "partitions": len(entries),
                "cohort_people": len(histories),
                "total_bytes": sum(entry["bytes"] for entry in entries),
                "largest_partition_bytes": max((entry["bytes"] for entry in entries), default=0),
                "coverage": "current_roster_only_not_all_historical_deputies",
                "activated": arguments.activate,
            }
        )
    )


if __name__ == "__main__":
    main()
