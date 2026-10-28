"""Publish expanding historical cohorts without creating unverified canonical people."""

import argparse
import json
from pathlib import Path

from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from service.political_dashboard_dataset.camara_full_history import (
    historical_universe_members,
    historical_universe_partitions,
)
from service.political_dashboard_dataset.camara_historical_evidence import load_historical_evidence
from service.political_dashboard_dataset.storage import store_partition, write_atomic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-storage", type=Path, default=Path("data/enrichment"))
    options = parser.parse_args()
    directory = Path("data/camara-full-history/evidence-manifests")
    directory.mkdir(parents=True, exist_ok=True)
    universe, histories, legislatures, manifests, digest = load_historical_evidence(
        options.source_storage, directory,
    )
    with connect_database(options.env_file) as connection, connection.transaction():
        repository = AnnualDashboardRepository(connection)
        identities = repository.fetch_verified_camara_identities()
        partitions = []
        for year in range(2000, 2026):
            members = historical_universe_members(
                histories, legislatures, identities, manifests, year,
            )
            partitions.extend(historical_universe_partitions(
                members, year, len(histories), len(universe["people"]), digest,
            ))
        require_monotonic_history(connection, partitions)
        directory = Path("data/political-dashboard")
        entries = [store_partition(directory, row) for row in partitions]
        repository.activate_partitions(partitions)
        write_atomic(directory / "camara-full-history-manifest.json", json.dumps(entries).encode())
    print(json.dumps({"partitions": len(entries), "archived_people": len(histories),
                      "universe_people": len(universe["people"]),
                      "national_counts": {row["year"]: row["total"] for row in partitions
                                          if row["territory_code"] == "BR"}}))


def require_monotonic_history(connection, partitions):
    existing = connection.execute(
        "SELECT year,territory_code,(payload->>'total')::integer AS total "
        "FROM se_liga_brasil.political_dashboard_annual WHERE institution_code='camara' "
        "AND year BETWEEN 2000 AND 2025 ORDER BY year,territory_code FOR UPDATE",
    ).fetchall()
    incoming = {(row["year"], row["territory_code"]): row["total"] for row in partitions}
    for row in existing:
        if incoming.get((row["year"], row["territory_code"]), 0) < (row["total"] or 0):
            raise ValueError("BROADER_CAMARA_HISTORY_MUST_NOT_DROP_VERIFIED_PEOPLE")


if __name__ == "__main__":
    main()
