"""Collect one bounded national Senate roster batch with canonical identity checks."""

import argparse
import json
from pathlib import Path

from crawlers.senado.roster_collection import (
    acquire_national_roster_batch,
    ingest_national_roster_batch,
)
from database.operations import connect_database, refresh_person_profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    arguments = parser.parse_args()
    with connect_database(arguments.env_file) as connection:
        configuration, acquired, roster_size = acquire_national_roster_batch(
            connection, arguments.storage, limit=arguments.limit, offset=arguments.offset
        )
        summaries = ingest_national_roster_batch(connection, configuration, acquired)
        refresh_person_profiles(connection)
    print(
        json.dumps(
            {
                "roster_size": roster_size,
                "offset": arguments.offset,
                "collected_profiles": len(acquired),
                "ingestion": summaries,
            }
        )
    )


if __name__ == "__main__":
    main()
