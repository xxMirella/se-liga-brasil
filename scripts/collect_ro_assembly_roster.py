"""Archive Rondônia's24official profiles, then publish their common roster if requested."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.alero.roster import parse_current_roster, parse_profile_party  # noqa: E402
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

URL = "https://www.al.ro.leg.br/deputados/perfil/"


def collect_verified_members(acquisition):
    roster = acquisition.acquire(URL)
    members = parse_current_roster(roster.path.read_bytes())
    evidence = []
    for member in members:
        profile = acquisition.acquire(member["official_url"], "assembly_member_profile")
        member["political_party"] = parse_profile_party(profile.path.read_bytes(), member["name"])
        evidence.append(
            {
                "url": member["official_url"],
                "sha256": profile.sha256,
                "fetched_at": profile.fetched_at,
            }
        )
        print(member["provider_subject_id"], flush=True)
    return members, {
        "url": URL,
        "sha256": roster.sha256,
        "fetched_at": roster.fetched_at,
        "supporting_evidence": evidence,
    }


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
            SourceDescriptor("alero", "ALERO", URL),
            frozenset({"www.al.ro.leg.br"}),
            RosterAcquisition,
        ) as acquisition:
            members, evidence = collect_verified_members(acquisition)
        partition = aggregate_current_roster(members, "alero", "RO", evidence)
        store_partition(Path("data/political-dashboard"), partition)
        save_json(configuration.storage_directory / "ro-verified-roster.json", partition)
        if options.activate:
            AnnualDashboardRepository(connection).activate_partitions([partition])
    print(f"RO verified members: {len(members)}; activated: {options.activate}", flush=True)


if __name__ == "__main__":
    main()
