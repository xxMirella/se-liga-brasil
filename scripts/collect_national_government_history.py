"""Download official dated governor observations into a separate mergeable evidence dataset."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.state_government.acquisition import StateGovernmentConfiguration
from crawlers.state_government.national_observations import NationalGovernmentAcquisition
from service.national_government_history.collection import collect_national_government_observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/national-government-history"))
    arguments = parser.parse_args()
    configuration = StateGovernmentConfiguration(arguments.storage)
    with httpx.Client() as client:
        acquisition = NationalGovernmentAcquisition(configuration, client)
        result = collect_national_government_observations(
            acquisition, arguments.storage / "historical-executive-evidence.json",
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
