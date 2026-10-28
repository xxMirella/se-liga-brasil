"""Acquire bounded, resumable official deputy histories without projecting unvalidated intervals."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.camara.cached_roster import load_cached_current_roster  # noqa: E402
from crawlers.camara.history_archives import collect_batch  # noqa: E402
from database.operations import connect_database  # noqa: E402
from storage.files import save_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--all", action="store_true")
    arguments = parser.parse_args()
    if not 1 <= arguments.limit <= 25 or arguments.offset < 0:
        raise ValueError("INVALID_CAMARA_HISTORY_BATCH")
    members, _ = load_cached_current_roster(arguments.storage)
    if not members:
        raise ValueError("VERIFIED_CURRENT_ROSTER_REQUIRED")
    members.sort(key=lambda row: int(row["id"]))
    for offset in range(arguments.offset, len(members), arguments.limit):
        with connect_database(arguments.env_file) as connection:
            reports = collect_batch(
                connection, arguments.storage, members[offset : offset + arguments.limit]
            )
        report = {"offset": offset, "next_offset": offset + len(reports), "people": reports}
        save_json(arguments.storage / "camara-history-checkpoint.json", report)
        print(json.dumps(report), flush=True)
        if not arguments.all:
            return


if __name__ == "__main__":
    from service.ingestion.contracts import IngestionError

    try:
        main()
    except IngestionError as error:
        print(json.dumps({"error": error.code, **error.details}), flush=True)
        raise SystemExit(1) from None
