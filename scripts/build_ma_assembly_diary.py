"""Publish Maranhão's dated official diary roster after source registry reconciliation."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawlers.alema.diary_roster import (  # noqa: E402
    extract_diary_text,
    match_diary_source_ids,
    october_publication_date,
    parse_diary_roster,
)
from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import AnnualDashboardRepository  # noqa: E402
from service.political_dashboard_dataset.storage import store_partition  # noqa: E402
from service.state_assembly_rosters.aggregation import aggregate_current_roster  # noqa: E402
from storage.files import hash_file, save_json  # noqa: E402

STORAGE = Path("data/state-assembly-rosters")
DIARY = "https://www.al.ma.leg.br/sitealema/wp-content/uploads/2026/10/Diario_182_26_10_2026.pdf"
REGISTRY = "https://alemalegis.al.ma.leg.br/api/v1/public/parliamentary/filter/legislature/20"


def verified_archive(url):
    manifests = [json.loads(p.read_text()) for p in (STORAGE / "manifests").glob("*.json")]
    matching = [m for m in manifests if m["source_url"] == url]
    if len(matching) != 1:
        raise ValueError("ALEMA_DIARY_ARCHIVE_MISSING_OR_AMBIGUOUS")
    manifest = matching[0]
    path = Path(manifest["path"]).resolve()
    if not path.is_relative_to((STORAGE / "archives").resolve()):
        raise ValueError("ALEMA_DIARY_ARCHIVE_OUTSIDE_STORAGE")
    if hash_file(path) != manifest["sha256"]:
        raise ValueError("ALEMA_DIARY_ARCHIVE_HASH_MISMATCH")
    evidence = {k: manifest[k] for k in ["sha256", "fetched_at"]}
    return path, {**evidence, "url": url}


def build_partition():
    diary_path, diary_evidence = verified_archive(DIARY)
    registry_path, registry_evidence = verified_archive(REGISTRY)
    roster = parse_diary_roster(
        extract_diary_text(diary_path), october_publication_date("2026-10-26")
    )
    members = match_diary_source_ids(roster["members"], json.loads(registry_path.read_text()))
    partition = aggregate_current_roster(members, "alema", "MA", diary_evidence)
    partition.update(
        snapshot_on=roster["observed_on"],
        observed_on=roster["observed_on"],
        evidence=[
            {**diary_evidence, "locator": "page 1; party/bloc roster; licensed column excluded"},
            registry_evidence,
        ],
        licensed_members=roster["licensed"],
        official_roster_publication_on=roster["observed_on"],
        coverage_limitation="official_published_roster_not_individual_attendance_confirmation",
        supersedes_directory_reason="directory_has_aluizio_active_and_fernando_licensed_and_omits_para",
    )
    return partition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    partition = build_partition()
    store_partition(Path("data/political-dashboard"), partition)
    save_json(STORAGE / "ma-diary-roster.json", partition)
    if args.activate:
        with connect_database(args.env_file) as connection:
            AnnualDashboardRepository(connection).activate_partitions([partition])
    print(
        json.dumps(
            {
                "uf": "MA",
                "total": partition["total"],
                "snapshot_on": partition["snapshot_on"],
                "activated": args.activate,
            }
        )
    )


if __name__ == "__main__":
    main()
