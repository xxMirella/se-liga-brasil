"""Collect official capital-city mayoral history for annual dashboard datasets."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.municipal_government.acquisition import (
    MunicipalGovernmentAcquisition,
    MunicipalGovernmentConfiguration,
)
from crawlers.municipal_government.catalog import SOURCES
from service.municipal_government_history.collection import collect_municipal_government_history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/municipal-government-history"))
    arguments = parser.parse_args()
    configuration = MunicipalGovernmentConfiguration(arguments.storage)
    with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
        acquisition = MunicipalGovernmentAcquisition(configuration, client)
        artifacts = {
            key: acquisition.acquire(url, uf, ".pdf" if url.endswith(".pdf") else ".html")
            for key, (uf, url) in SOURCES.items()
        }
    print(
        json.dumps(
            collect_municipal_government_history(
                artifacts, arguments.storage / "historical-executive-evidence.json"
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
