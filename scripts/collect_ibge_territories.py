"""Materialize the official national state/municipality lookup outside dashboard requests."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.ibge.territories import TerritoryConfiguration, collect_current_territories
from service.presidential_history.source_inventory import build_national_collection_inventory
from storage.files import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/ibge-territories"))
    arguments = parser.parse_args()
    configuration = TerritoryConfiguration(arguments.storage)
    with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
        payload = collect_current_territories(configuration, client)
    inventory = build_national_collection_inventory(
        payload, through_year=int(payload["observed_at"][:4]),
    )
    save_json(arguments.storage / "political-source-inventory.json", inventory)
    print(json.dumps({"states": len(payload["states"]),
                      "municipalities": len(payload["municipalities"]),
                      "special_districts": len(payload["special_districts"])}))


if __name__ == "__main__":
    main()
