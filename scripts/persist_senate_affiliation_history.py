"""Import an archived official affiliation response; no name-based identity association."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from database.senate_affiliation_history import persist_senate_affiliation_history
from service.senate_history.affiliation_intervals import parliamentary_affiliation_intervals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--senator-code", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    options = parser.parse_args()
    raw = options.archive.read_bytes()
    intervals = parliamentary_affiliation_intervals(json.loads(raw), options.senator_code)
    with connect_database(options.env_file) as connection:
        result = persist_senate_affiliation_history(
            connection, options.senator_code, raw, intervals, options.archive,
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
