"""Acquire and publish actual dated Senate exercises and affiliations by year."""

import argparse
import json
from datetime import date
from pathlib import Path

import httpx

from crawlers.senado.historical_acquisition import (
    SenateHistoryAcquisition,
    SenateHistoryConfiguration,
)
from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from database.senate_history import fetch_verified_senator_identities
from service.senate_history.collection import (
    associate_verified_senators,
    build_senate_history_partitions,
    collect_affiliations,
    collect_exercises,
    publish_senate_history,
    save_senate_history_evidence,
)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/senate-history"))
    parser.add_argument("--dataset-storage", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--first-legislature", type=int, default=21)
    parser.add_argument("--last-legislature", type=int, default=57)
    parser.add_argument("--first-year", type=int, default=1889)
    parser.add_argument("--last-year", type=int, default=date.today().year - 1)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--activate", action="store_true")
    return parser.parse_args()


def progress(event):
    print(json.dumps(event), flush=True)


def main():
    options = arguments()
    if not 1889 <= options.first_year <= options.last_year < date.today().year:
        raise ValueError("HISTORICAL_COLLECTION_MUST_PRESERVE_CURRENT_YEAR_SNAPSHOT")
    configuration = SenateHistoryConfiguration(options.storage)
    with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
        acquisition = SenateHistoryAcquisition(configuration, client)
        exercises, coverage = collect_exercises(acquisition, range(
            options.first_legislature, options.last_legislature + 1
        ), progress)
        affiliations = collect_affiliations(acquisition, exercises, progress)
    save_senate_history_evidence(options.storage, exercises, affiliations, coverage)
    partitions = build_senate_history_partitions(
        exercises, affiliations, options.first_year, options.last_year
    )
    if options.activate:
        with connect_database(options.env_file) as connection:
            associate_verified_senators(partitions, fetch_verified_senator_identities(connection))
            entries = publish_senate_history(
                partitions, options.dataset_storage, AnnualDashboardRepository(connection)
            )
    else:
        entries = publish_senate_history(partitions, options.dataset_storage)
    progress({"stage": "completed", "exercises": len(exercises),
              "people": len(affiliations), "partitions": len(entries),
              "activated": options.activate})


if __name__ == "__main__":
    main()
