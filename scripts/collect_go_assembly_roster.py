"""Collect Goiás' HTML sources and publish a dated, explicitly qualified reconciliation."""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.alego.roster import reconcile_current_roster  # noqa: E402
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
    "https://portal.al.go.leg.br/deputados/em-exercicio",
    "https://portal.al.go.leg.br/deputados/fora-exercicio",
    "https://portal.al.go.leg.br/noticias/167603",
]


@dataclass(frozen=True)
class AlegoHtmlConfiguration(RosterConfiguration):
    request_accept: str = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"


def qualified_partition(artifacts):
    observed_on = (
        datetime.fromisoformat(artifacts[0].fetched_at).astimezone(ZoneInfo("America/Belem")).date()
    )
    members, excluded = reconcile_current_roster(
        *(artifact.path.read_bytes() for artifact in artifacts), observed_on
    )
    evidence = [
        {"url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at}
        for url, artifact in zip(URLS, artifacts, strict=True)
    ]
    partition = aggregate_current_roster(members, "alego", "GO", evidence[0])
    partition.update(
        aggregation_basis="official_roster_reconciled_with_dated_exercise_evidence",
        coverage="observed_partial",
        snapshot_on=None,
        evidence=evidence,
        coverage_limitation="directory_observed_2026_10_27_reconciled_with_dated_return_2026_10_07",
        last_exercise_evidence_on="2026-10-07",
        reconciled_records_count=41,
        source_directory_size=43,
        excluded_directory_members=excluded,
        political_party_limitation="labels_observed_in_directory_not_continuous_affiliation_proof",
        annual_cohort="reconciled_directory_with_dated_death_and_substitute_return",
    )
    return partition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--activate", action="store_true")
    options = parser.parse_args()
    storage = Path("data/state-assembly-rosters").resolve()
    configuration = AlegoHtmlConfiguration(storage)
    with connect_database(options.env_file) as connection:
        with official_source_acquisition(
            connection,
            configuration,
            SourceDescriptor("alego", "ALEGO", URLS[0]),
            frozenset({"portal.al.go.leg.br"}),
            RosterAcquisition,
        ) as acquisition:
            artifacts = [acquisition.acquire(url) for url in URLS]
        partition = qualified_partition(artifacts)
        store_partition(Path("data/political-dashboard"), partition)
        save_json(storage / "go-reconciled-roster.json", partition)
        if options.activate:
            AnnualDashboardRepository(connection).activate_partitions([partition])
    print(
        json.dumps({"uf": "GO", "records": 41, "snapshot_on": None, "activated": options.activate})
    )


if __name__ == "__main__":
    main()
