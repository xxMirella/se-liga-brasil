"""Fetch official historical evidence for the dashboard; never fabricate party affiliation."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.presidency.acquisition import PresidencyAcquisition, PresidencyConfiguration
from service.presidential_history.archive_collection import collect_national_presidential_archive
from service.presidential_history.collection import collect_presidential_chronology


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/presidency-history"))
    parser.add_argument("--source", choices=("archive", "first-republic"), default="archive")
    arguments = parser.parse_args()
    configuration = PresidencyConfiguration(arguments.storage)
    with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
        acquisition = PresidencyAcquisition(configuration, client)
        collect = collect_national_presidential_archive if arguments.source == "archive" else (
            collect_presidential_chronology)
        result = collect(
            acquisition, arguments.storage / "historical-executive-evidence.json",
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
