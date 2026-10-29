"""Reconcile and activate 2010–2019 Chamber snapshots, preserving 2020–2026."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from crawlers.camara.legacy_reconciliation import load_legacy_reconciliation
from database.operations import connect_database
from database.political_dashboard_analytical import AnnualDashboardRepository
from service.political_dashboard.camara_orientation import chamber_orientation_summary
from service.political_dashboard_dataset.camara_full_history import (
    historical_universe_members,
    historical_universe_partition,
)
from service.political_dashboard_dataset.camara_historical_evidence import load_historical_evidence
from service.political_dashboard_dataset.chamber_capacity import SEATS_BY_UF as SEATS
from service.political_dashboard_dataset.chamber_changes import dated_chamber_changes
from service.political_dashboard_dataset.chamber_reconciliation import (
    reconciliation_by_uf,
    supplement_historical_members,
    verified_historical_vacancies,
)
from service.political_dashboard_dataset.chamber_reconciliation_audit import (
    nominal_reconciliation_audit,
)
from service.political_dashboard_dataset.storage import store_partition, write_atomic

POLICY_VERSION = "camara_2010_2019.v2"


def write_json(path, value):
    write_atomic(path, json.dumps(value, ensure_ascii=False, indent=2, default=str).encode())


def build_reconciled_partitions(options, identities):
    universe, histories, legislatures, manifests, digest = load_historical_evidence(
        options.source_storage, options.storage / "evidence-manifests",
    )
    records = load_legacy_reconciliation(
        getattr(options, "evidence_storage", None) or options.storage,
    )
    partitions, audits = [], []
    for year in range(2010, 2020):
        members = historical_universe_members(histories, legislatures, identities, manifests, year)
        baseline = len(members)
        cases = supplement_historical_members(members, histories, records, legislatures,
                                             identities, manifests, year)
        vacancies = verified_historical_vacancies(histories, records, legislatures,
                                                 members, SEATS, year)
        reconciliation = reconciliation_by_uf(members, vacancies, SEATS)
        partition = historical_universe_partition(members, year, "BR", len(histories),
                                                   len(universe["people"]), digest)
        crosswalk, pending = nominal_reconciliation_audit(
            histories, legislatures, members, reconciliation, year,
        )
        write_json(options.storage / "crosswalk" / f"{year}.json", crosswalk)
        write_json(options.storage / "pending" / f"{year}.json", pending)
        partition["uf_reconciliation"] = reconciliation
        partition["reconciliation_pending"] = [{key: row[key] for key in (
            "source_person_id", "name", "uf", "official_url",
        )} for row in pending]
        partition.update(orientation_policy_version=POLICY_VERSION,
                         documented_vacancies=vacancies,
                         within_year_changes=dated_chamber_changes(
                             histories, year, f"{year}-12-31",
                         ))
        complete = all(row["unresolved"] == 0 for row in reconciliation)
        partition["coverage"] = "observed_complete" if complete else "observed_partial"
        partition["coverage_detail"] = (
            "Exercício datado REST conciliado com períodos legados oficiais; "
            "vagas só com saída definitiva e vínculo explícito ao sucessor empossado depois. "
            "Condição eleitoral, função na Mesa e cadeira não são conceitos equivalentes."
        )
        partitions.append(partition)
        audits.append({"year": year, "baseline_people": baseline, "reconciled_cases": cases,
                       "uf_reconciliation": reconciliation, "vacancies": vacancies,
                       "orientation": chamber_orientation_summary(partition, year)})
    return partitions, audits


def activate_reconciled_partitions(connection, repository, partitions, storage):
    previous = connection.execute(
        "SELECT year,territory_code,institution_code,payload,content_sha256 "
        "FROM se_liga_brasil.political_dashboard_annual WHERE institution_code='camara' "
        "AND territory_code='BR' AND year BETWEEN 2010 AND 2026 ORDER BY year FOR UPDATE",
    ).fetchall()
    indexed = {row["year"]: row["payload"] for row in previous}
    for partition in partitions:
        old_ids = {row["source_person_id"] for row in indexed.get(partition["year"], {}).get(
            "members", []) if row.get("source_person_id")}
        new_ids = {row["source_person_id"] for row in partition["members"]}
        if not old_ids <= new_ids:
            raise ValueError("CHAMBER_RECONCILIATION_WOULD_DROP_EXISTING_PEOPLE")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(storage / f"before-integration-{timestamp}.json", previous)
    preserved = {row["year"]: row["content_sha256"] for row in previous if row["year"] >= 2020}
    repository.activate_partitions(partitions)
    current = connection.execute(
        "SELECT year,content_sha256 FROM se_liga_brasil.political_dashboard_annual "
        "WHERE institution_code='camara' AND territory_code='BR' AND year BETWEEN 2020 AND 2026",
    ).fetchall()
    if {row["year"]: row["content_sha256"] for row in current} != preserved:
        raise ValueError("CHAMBER_RECONCILIATION_CHANGED_2020_2026")
    return preserved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--storage", type=Path,
                        default=Path("data/camara-reconciliation-2010-2026"))
    parser.add_argument("--evidence-storage", type=Path)
    parser.add_argument("--apply", action="store_true")
    options = parser.parse_args()
    options.storage.mkdir(parents=True, exist_ok=True)
    with connect_database(options.env_file) as connection, connection.transaction():
        repository = AnnualDashboardRepository(connection)
        partitions, audits = build_reconciled_partitions(options,
                                                        repository.fetch_verified_camara_identities())
        entries = [store_partition(options.storage / "partitions", row) for row in partitions]
        preserved = activate_reconciled_partitions(connection, repository, partitions,
                                                  options.storage) if options.apply else {}
    write_json(options.storage / "annual-manifest.json", entries)
    write_json(options.storage / "audit.json", audits)
    result = {"applied": options.apply, "preserved_2020_2026": preserved,
              "years": [{"year": row["year"], "people": row["orientation"]["observed_people"],
                         "vacancies": len(row["vacancies"]),
                         "unresolved": row["orientation"]["unobserved_seats"]} for row in audits]}
    write_json(options.storage / "activation.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
