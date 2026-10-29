"""Drop the published dashboard history table; the application then rebuilds it on the fly.

Default is a dry run (reports whether the table exists). `--apply` drops it. Annual
partitions are never touched.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import PROJECT_ROOT, connect_database  # noqa: E402
from database.political_dashboard_history import DashboardHistoryTable  # noqa: E402

ROLLBACK = PROJECT_ROOT / "db/rollbacks/political_dashboard_history_rollback.sql"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true", help="drop the table; default is a dry run")
    arguments = parser.parse_args()
    with connect_database(arguments.env_file) as connection:
        existed = DashboardHistoryTable(connection).is_available()
        if arguments.apply:
            with connection.transaction():
                connection.execute(ROLLBACK.read_text(encoding="utf-8"))
    print(json.dumps({
        "mode": "apply" if arguments.apply else "dry-run (nothing dropped)",
        "table_existed": existed, "dropped": bool(arguments.apply and existed),
    }))


if __name__ == "__main__":
    main()
