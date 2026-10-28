"""Publish only the offline, source-validated IBGE catalog partitioned by UF."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import AnnualDashboardRepository  # noqa: E402
from service.political_dashboard_dataset.territories import build_territorial_catalogs  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    arguments = parser.parse_args()
    partitions = build_territorial_catalogs(json.loads(arguments.catalog.read_text()))
    with connect_database(arguments.env_file) as connection:
        migration = Path(__file__).resolve().parents[1] / "db/political_dashboard_annual.sql"
        connection.execute(migration.read_text())
        AnnualDashboardRepository(connection).activate_territorial_catalogs(partitions)
    print(
        json.dumps(
            {
                "uf_partitions": len(partitions),
                "municipalities": sum(len(partition["municipalities"]) for partition in partitions),
            }
        )
    )


if __name__ == "__main__":
    main()
