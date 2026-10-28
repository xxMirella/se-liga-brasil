"""Expand dated status histories to all people in the official historical legislature universe."""

import argparse
import json
from pathlib import Path

from crawlers.camara.historical_universe import collect_historical_deputy_universe
from crawlers.camara.history_archives import collect_batch, read_verified_history
from database.operations import connect_database
from service.ingestion.contracts import IngestionError
from storage.files import save_json


def existing_history_is_verified(storage, identifier):
    if not (storage / "camara-history" / f"{identifier}.json").is_file():
        return False
    read_verified_history(storage, identifier)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--all", action="store_true")
    options = parser.parse_args()
    if not 1 <= options.limit <= 25:
        raise ValueError("INVALID_CAMARA_HISTORY_BATCH")
    source = options.storage / "camara-historical-universe.json"
    if options.discover or not source.exists():
        with connect_database(options.env_file) as connection:
            collect_historical_deputy_universe(connection, options.storage, range(51, 58))
    universe = json.loads(source.read_text())
    if universe["schema_version"] != "camara_historical_universe.v1":
        raise ValueError("UNSUPPORTED_CAMARA_HISTORICAL_UNIVERSE")
    pending = [row for row in universe["people"]
               if not existing_history_is_verified(options.storage, row["id"])]
    for offset in range(0, len(pending), options.limit):
        with connect_database(options.env_file) as connection:
            records = collect_batch(
                connection, options.storage, pending[offset:offset + options.limit],
                cohort="historical_legislature_roster_union_not_current_roster_only",
            )
        report = {"universe_people": len(universe["people"]), "pending_at_start": len(pending),
                  "next_offset": offset + len(records), "people": records}
        save_json(options.storage / "camara-full-history-checkpoint.json", report)
        print(json.dumps(report), flush=True)
        if not options.all:
            return


if __name__ == "__main__":
    try:
        main()
    except IngestionError as error:
        print(json.dumps({"error": error.code, **error.details}), flush=True)
        raise SystemExit(1) from None
