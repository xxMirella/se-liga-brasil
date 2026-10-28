"""Collect bounded ALERJ synopsis documents for an independently verified person."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from service.alerj_history.collection import collect_alerj_history
from service.ingestion.contracts import IngestionError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--profile-url", required=True)
    parser.add_argument("--senator-code", required=True)
    parser.add_argument("--synopsis-url", action="append", required=True)
    parser.add_argument("--offline", action="store_true")
    arguments = parser.parse_args()
    try:
        with connect_database(arguments.env_file) as connection:
            result = collect_alerj_history(
                connection,
                arguments.storage,
                arguments.person_id,
                arguments.profile_url,
                arguments.senator_code,
                arguments.synopsis_url,
                offline=arguments.offline,
            )
    except IngestionError as error:
        print(json.dumps({"status": "blocked", "code": error.code, "details": error.details}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
