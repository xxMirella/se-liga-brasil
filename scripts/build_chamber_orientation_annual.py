"""Verify archived Chamber evidence and integrate 2020–2026 into existing annual projections."""

import argparse
import json
from datetime import date
from pathlib import Path

from crawlers.camara.dated_roster import load_dated_roster
from crawlers.camara.legacy_exercises import (
    corroborated_legacy_entry,
    read_verified_legacy_periods,
)
from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from service.political_dashboard.camara_orientation import chamber_orientation_summary
from service.political_dashboard_dataset.camara_full_history import (
    historical_source_member,
    historical_universe_members,
    historical_universe_partition,
)
from service.political_dashboard_dataset.camara_historical_evidence import load_historical_evidence
from service.political_dashboard_dataset.chamber_capacity import SEATS_BY_UF
from service.political_dashboard_dataset.chamber_changes import dated_chamber_changes
from service.political_dashboard_dataset.chamber_reconciliation import reconciliation_by_uf
from service.political_dashboard_dataset.chamber_vacancies import chamber_2020_vacancy
from service.political_dashboard_dataset.storage import store_partition, write_atomic

CUTOFF = date(2026, 10, 29)


def build_current_partition(storage, identities, archived, universe, digest):
    roster, evidence, observed = load_dated_roster(storage, CUTOFF)
    members = []
    for row in roster:
        identifier = str(row["id"])
        identity = identities.get(identifier)
        members.append({"person_id": identity["person_id"] if identity else "camara:" + identifier,
                        "source_person_id": identifier, "name": row["nome"],
                        "political_party": row["siglaPartido"], "uf": row["siglaUf"],
                        "official_url": row["uri"],
                        "political_party_source_uri": row["uriPartido"]})
    partition = historical_universe_partition(members, 2026, "BR", archived, universe, digest)
    partition.update({key: observed.isoformat() for key in (
        "observed_on", "observed_from", "snapshot_on", "reference_on")})
    partition.update(aggregation_basis="verified_dated_official_current_roster",
                     annual_cohort="current_roster_snapshot_not_full_year_occupancy",
                     evidence=evidence, coverage_detail="Listagem oficial em exercício; "
                     "paginação integral, identificadores únicos e data comum verificados.")
    return partition


def build_partitions(options, identities):
    directory = options.storage / "evidence-manifests"
    directory.mkdir(parents=True, exist_ok=True)
    universe, histories, legislatures, manifests, digest = load_historical_evidence(
        options.source_storage, directory,
    )
    legacy = read_verified_legacy_periods(options.storage)
    partitions = []
    for year in range(2020, 2026):
        members = historical_universe_members(histories, legislatures, identities, manifests, year)
        members = supplement_legacy_members(
            members, histories, legacy, identities, manifests, year,
        )
        partition = historical_universe_partition(
            members, year, "BR", len(histories), len(universe["people"]), digest,
        )
        if year == 2020 and len(members) == 512:
            partition["documented_vacancies"] = [chamber_2020_vacancy(histories, manifests)]
            partition["coverage"] = "observed_complete"
            partition["coverage_detail"] = (
                "Universo e históricos oficiais verificados. "
                "Conciliação: 512 em exercício e uma vaga ES em 31/12/2020; "
                "renúncia de Sergio Vidigal e posse de Neucimar Fraga em 01/01/2021."
            )
        partitions.append(partition)
    partitions.append(build_current_partition(
        options.storage, identities, len(histories), len(universe["people"]), digest,
    ))
    for partition in partitions:
        partition["within_year_changes"] = dated_chamber_changes(
            histories, partition["year"], partition["snapshot_on"],
        )
        partition["orientation_policy_version"] = "camara_2020_2026.v1"
        partition["uf_reconciliation"] = reconciliation_by_uf(
            partition["members"], partition.get("documented_vacancies") or [],
            SEATS_BY_UF,
        )
    return partitions



def supplement_legacy_members(members, histories, legacy, identities, manifests, year):
    existing = {member["source_person_id"] for member in members}
    for history in histories:
        identifier = history["official_deputy_id"]
        if identifier in existing or identifier not in legacy:
            continue
        record = legacy[identifier]
        status = corroborated_legacy_entry(history, record, year)
        if status is None:
            continue
        member = historical_source_member(history, status, identities, manifests)
        member.update(exercise_source_sha256=record["evidence"]["sha256"],
                      exercise_source_url=record["evidence"]["url"],
                      exercise_method="legacy_interval_corroborates_rest_reassumption")
        members.append(member)
        existing.add(identifier)
    return members


def preserve_existing_partitions(connection, storage):
    rows = connection.execute(
        "SELECT year,territory_code,institution_code,payload,content_sha256 "
        "FROM se_liga_brasil.political_dashboard_annual WHERE institution_code='camara' "
        "AND territory_code='BR' AND year BETWEEN 2020 AND 2026 ORDER BY year FOR UPDATE",
    ).fetchall()
    destination = storage / "before-integration.json"
    if not destination.exists():
        write_atomic(destination, json.dumps(rows, ensure_ascii=False).encode())
    return {row["year"]: row["payload"] for row in rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--storage", type=Path, default=Path("data/camara-orientation-2020-2026"))
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    with connect_database(options.env_file) as connection, connection.transaction():
        repository = AnnualDashboardRepository(connection)
        partitions = build_partitions(options, repository.fetch_verified_camara_identities())
        entries = [store_partition(options.storage / "partitions", row) for row in partitions]
        write_atomic(options.storage / "annual-manifest.json", json.dumps(entries).encode())
        if options.apply:
            previous = preserve_existing_partitions(connection, options.storage)
            for row in partitions:
                if row["total"] < previous.get(row["year"], {}).get("total", 0):
                    raise ValueError("CHAMBER_INTEGRATION_WOULD_DROP_VERIFIED_PEOPLE")
            repository.activate_partitions(partitions)
    summaries = {row["year"]: chamber_orientation_summary(row, row["year"]) for row in partitions}
    write_atomic(options.storage / "audit.json", json.dumps(summaries, ensure_ascii=False,
                                                            indent=2).encode())
    print(json.dumps({"applied": options.apply, "years": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
