"""Fetch older official legislature rolls without inventing continuous exercise dates."""

import json
from pathlib import Path

import httpx

from crawlers.senado.historical_acquisition import (
    SenateHistoryAcquisition,
    SenateHistoryConfiguration,
)
from service.senate_history.rosters import collect_legislature_rosters
from storage.files import save_json


def main():
    directory = Path("data/senate-history")
    configuration = SenateHistoryConfiguration(directory)
    with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
        rows = collect_legislature_rosters(
            SenateHistoryAcquisition(configuration, client), range(1, 49),
            lambda value: print(json.dumps(value), flush=True),
        )
    save_json(directory / "historical-legislature-rosters.json", {
        "schema_version": "historical_senate_rosters.v1", "rosters": rows,
        "semantics": "Documented legislature membership, not simultaneous annual seats",
    })


if __name__ == "__main__":
    main()
