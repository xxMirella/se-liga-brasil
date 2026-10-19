"""Explicit, repeatable profile photo maintenance command; dry run by default."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from database.profile_media import ProfileMediaRepository
from service.profile_media.backfill import backfill_profile_photos, summarize_profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--data-directory", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    with connect_database(arguments.env_file) as connection:
        repository = ProfileMediaRepository(connection)
        result = backfill_profile_photos(
            repository, arguments.data_directory, limit=arguments.limit, apply=arguments.apply
        )
        result["after"] = summarize_profiles(
            repository.fetch_linked_profiles(arguments.limit)[: arguments.limit]
        )
        result["person_coverage"] = repository.fetch_person_photo_coverage()
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
