"""Reconcile RR's25directorycards with the formal replacement and dated governor observation."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.alrr.reconciliation import reconcile_current_directory  # noqa: E402
from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import AnnualDashboardRepository  # noqa: E402
from service.ingestion.contracts import SourceDescriptor  # noqa: E402
from service.political_dashboard_dataset.storage import store_partition  # noqa: E402
from service.state_assembly_rosters.acquisition import (  # noqa: E402
    RosterAcquisition,
    RosterConfiguration,
)
from service.state_assembly_rosters.aggregation import aggregate_current_roster  # noqa: E402
from service.voting_pipeline.runtime import official_source_acquisition  # noqa: E402
from storage.files import save_json  # noqa: E402

URLS = [
    "https://al.rr.leg.br/deputados-estaduais-2023/",
    "https://al.rr.leg.br/2026/05/05/parlamento-mesa-diretora-empossa-rogerio-borges-no-cargo-de-deputado-estadual/",
    "https://portal.rr.gov.br/governador-soldado-sampaio-recebe-arthur-henrique-e-autoriza-compartilhamento-de-dados-com-nova-equipe/",
]


def qualified_partition(artifacts):
    members, excluded = reconcile_current_directory(*(a.path.read_bytes() for a in artifacts))
    evidence = [
        {"url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at}
        for url, artifact in zip(URLS, artifacts, strict=True)
    ]
    partition = aggregate_current_roster(members, "alrr", "RR", evidence[0])
    if partition["year"] != 2026:
        raise ValueError("ALRR_DATED_RECONCILIATION_REQUIRES_2026_OBSERVATION")
    partition.update(
        aggregation_basis="official_roster_reconciled_with_dated_exercise_evidence",
        coverage="observed_partial",
        snapshot_on=None,
        evidence=evidence,
        coverage_limitation="mixed_roster_2026_10_23_and_exercise_evidence_through_2026_10_15",
        last_exercise_evidence_on="2026-10-15",
        reconciled_records_count=len(members),
        source_directory_size=25,
        annual_cohort="reconciled_directory_with_dated_government_exclusion",
        excluded_directory_members=[
            {
                "name": excluded["name"],
                "source_subject_id": excluded["provider_subject_id"],
                "reason": (
                    "formal_replacement_by_rogerio_borges_2026_05_05_"
                    "and_governor_observed_2026_10_15"
                ),
                "evidence_urls": URLS[1:],
            }
        ],
    )
    return partition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--activate", action="store_true")
    options = parser.parse_args()
    configuration = RosterConfiguration(Path("data/state-assembly-rosters").resolve())
    with connect_database(options.env_file) as connection:
        with official_source_acquisition(
            connection,
            configuration,
            SourceDescriptor("alrr", "ALRR", URLS[0]),
            frozenset({"al.rr.leg.br", "portal.rr.gov.br"}),
            RosterAcquisition,
        ) as acquisition:
            artifacts = [acquisition.acquire(url, "assembly_exercise_status") for url in URLS]
        partition = qualified_partition(artifacts)
        store_partition(Path("data/political-dashboard"), partition)
        save_json(configuration.storage_directory / "rr-reconciled-roster.json", partition)
        if options.activate:
            AnnualDashboardRepository(connection).activate_partitions([partition])
    print("RR24 records reconciled; latest exercise proof15October2026; snapshot=None", flush=True)


if __name__ == "__main__":
    main()
