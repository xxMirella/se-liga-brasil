"""Archive official SP/RJ chronology evidence and normalize inputs for annual dashboard jobs."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.state_government.acquisition import (
    StateGovernmentAcquisition,
    StateGovernmentConfiguration,
)
from crawlers.state_government.catalog import SOURCES
from service.state_government_history.collection import collect_state_government_history
from service.state_government_history.verified_periods import verified_periods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/state-government-history"))
    arguments = parser.parse_args()
    configuration = StateGovernmentConfiguration(arguments.storage)
    with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
        acquisition = StateGovernmentAcquisition(configuration, client)
        artifacts = {
            key: acquisition.acquire(url, uf, ".pdf" if url.endswith(".pdf") else ".html")
            for key, (uf, url) in SOURCES.items()
        }
    result = collect_state_government_history(
        artifacts,
        arguments.storage / "historical-executive-evidence.json",
        verified_periods(artifacts),
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
