"""Build bounded yearly projections offline, then atomically activate the database generation."""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.camara.cached_roster import (  # noqa: E402
    coherent_roster_observed_on,
    load_cached_current_roster,
)
from database.operations import connect_database  # noqa: E402
from database.political_dashboard import PoliticalDashboardRepository  # noqa: E402
from database.political_dashboard_analytical import (  # noqa: E402
    AnnualDashboardRepository,
    serialize_manifest,
)
from service.political_dashboard_dataset.aggregation import build_annual_partitions  # noqa: E402
from service.state_assembly_rosters.aggregation import preserve_official_assembly_rosters  # noqa: E402
from service.political_dashboard_dataset.current_rosters import (
    current_camara_roster_partitions,  # noqa: E402
)
from service.political_dashboard_dataset.storage import store_partition, write_atomic  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--source-storage", type=Path, default=Path("data/enrichment"))
    arguments = parser.parse_args()
    if not 1889 <= arguments.year <= date.today().year:
        parser.error("Year must be between 1889 and the current year")
    started = time.perf_counter()
    with connect_database(arguments.env_file) as connection:
        rows = PoliticalDashboardRepository(connection).fetch_observations(
            None, date(arguments.year, 1, 1), date(arguments.year, 12, 31)
        )
        partitions = build_annual_partitions(rows, arguments.year)
        members, artifacts = load_cached_current_roster(arguments.source_storage)
        observed_on = coherent_roster_observed_on(artifacts)
        if observed_on and observed_on.year == arguments.year:
            roster_partitions = current_camara_roster_partitions(
                members,
                artifacts,
                AnnualDashboardRepository(connection).fetch_verified_camara_identities(),
                observed_on,
            )
            replacements = {
                (item["territory_code"], item["institution_code"]): item
                for item in roster_partitions
            }
            partitions = [
                item
                for item in partitions
                if (item["territory_code"], item["institution_code"]) not in replacements
            ]
            partitions.extend(roster_partitions)
        official = AnnualDashboardRepository(connection).fetch_current_official_assembly_rosters(
            arguments.year
        )
        partitions = preserve_official_assembly_rosters(partitions, official)
        entries = [store_partition(arguments.storage, partition) for partition in partitions]
        if arguments.activate:
            migration = Path(__file__).resolve().parents[1] / "db/political_dashboard_annual.sql"
            connection.execute(migration.read_text())
            AnnualDashboardRepository(connection).activate_partitions(partitions)
    arguments.storage.mkdir(parents=True, exist_ok=True)
    manifest = serialize_manifest(entries)
    write_atomic(arguments.storage / f"manifest-{arguments.year}.json", manifest.encode())
    print(
        json.dumps(
            {
                "year": arguments.year,
                "source_observations": len(rows),
                "partitions": len(entries),
                "total_partition_bytes": sum(entry["bytes"] for entry in entries),
                "largest_partition_bytes": max((entry["bytes"] for entry in entries), default=0),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "activated": arguments.activate,
            }
        )
    )


if __name__ == "__main__":
    main()
