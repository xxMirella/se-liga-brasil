"""Collect a bounded current federal Chamber roster with canonical personal evidence."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.camara.roster_collection import (  # noqa: E402
    acquire_national_roster_batch,
    ingest_national_roster_batch,
)
from database.operations import connect_database  # noqa: E402
from storage.files import save_json  # noqa: E402


def collect_selected_batches(arguments):
    offset = arguments.offset
    while offset < 1000:
        with connect_database(arguments.env_file) as connection:
            configuration, acquired, count = acquire_national_roster_batch(
                connection, arguments.storage, limit=arguments.limit, offset=offset
            )
            summaries = ingest_national_roster_batch(connection, configuration, acquired)
        report = {
            "roster_size": count,
            "offset": offset,
            "collected_profiles": len(acquired),
            "ingestion": summaries,
            "next_offset": min(offset + arguments.limit, count),
        }
        save_json(arguments.storage / "camara-roster-checkpoint.json", report)
        print(json.dumps(report), flush=True)
        if not arguments.all or offset + arguments.limit >= count:
            return
        offset += arguments.limit
    raise ValueError("CAMARA_ROSTER_SIZE_BUDGET_EXCEEDED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--all", action="store_true", help="Continue bounded batches until roster ends"
    )
    collect_selected_batches(parser.parse_args())


if __name__ == "__main__":
    main()
