"""Daily job: atomically rebuild the registered serving datasets (no-op while none exist)."""

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from service.serving import rebuild_serving_datasets  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    arguments = parser.parse_args()
    with connect_database(arguments.env_file) as connection:
        outcomes = rebuild_serving_datasets(connection, arguments.as_of)
    print(json.dumps({"as_of": arguments.as_of.isoformat(), "datasets": outcomes}))
    if any(value.startswith("failed:") for value in outcomes.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
