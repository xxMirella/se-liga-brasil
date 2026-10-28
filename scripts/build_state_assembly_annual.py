"""Publish common-roster current compositions without matching people by name."""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from database.political_dashboard_analytical import AnnualDashboardRepository  # noqa: E402
from database.state_assembly_rosters import StateAssemblyRosterRepository  # noqa: E402
from service.political_dashboard_dataset.storage import store_partition  # noqa: E402
from service.state_assembly_rosters.aggregation import (  # noqa: E402
    aggregate_current_roster,
    preserve_dated_ma_diary,
)
from service.state_assembly_rosters.identities import verified_subject_identities  # noqa: E402
from service.state_assembly_rosters.sources import PARSERS, SOURCE_URLS  # noqa: E402
from storage.files import hash_file  # noqa: E402

SOURCES = {uf: (SOURCE_URLS[uf][0], parse) for uf, parse in PARSERS.items()}


def load_source(storage, uf):
    receipt = storage / "roster-receipts" / f"{uf}.json"
    if receipt.exists():
        manifest = json.loads(receipt.read_text())
        if manifest["uf"] != uf or manifest["institution_code"] != SOURCE_URLS[uf][0]:
            raise ValueError("OFFICIAL_ASSEMBLY_RECEIPT_IDENTITY_MISMATCH")
        if urlsplit(manifest["source_url"]).hostname != urlsplit(SOURCE_URLS[uf][1]).hostname:
            raise ValueError("OFFICIAL_ASSEMBLY_RECEIPT_HOST_MISMATCH")
        return read_verified_archive(manifest, storage)
    matches = [
        json.loads(path.read_text())
        for path in (storage / "manifests").glob("*.json")
        if SOURCE_URLS[uf][1] == json.loads(path.read_text())["source_url"]
    ]
    if len(matches) != 1:
        raise ValueError("OFFICIAL_ASSEMBLY_ROSTER_ARCHIVE_MISSING_OR_AMBIGUOUS")
    manifest = matches[0]
    return read_verified_archive(manifest, storage)


def read_verified_archive(manifest, storage):
    path = Path(manifest["path"]).resolve()
    if not path.is_relative_to((storage / "archives").resolve()):
        raise ValueError("OFFICIAL_ASSEMBLY_ARCHIVE_OUTSIDE_STORAGE")
    if hash_file(path) != manifest["sha256"]:
        raise ValueError("OFFICIAL_ASSEMBLY_ROSTER_ARCHIVE_HASH_MISMATCH")
    return path.read_bytes(), {
        "url": manifest["source_url"],
        "sha256": manifest.get("source_sha256", manifest["sha256"]),
        "fetched_at": manifest["fetched_at"],
        "supporting_evidence": manifest.get("supporting_evidence", []),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-storage", type=Path, default=Path("data/state-assembly-rosters"))
    parser.add_argument("--storage", type=Path, default=Path("data/political-dashboard"))
    parser.add_argument("--uf", nargs="+", choices=SOURCES, default=list(SOURCES))
    parser.add_argument("--activate", action="store_true")
    arguments = parser.parse_args()
    partitions = []
    with connect_database(arguments.env_file) as connection:
        for uf in arguments.uf:
            institution, parse = SOURCES[uf]
            payload, evidence = load_source(arguments.source_storage, uf)
            identities = {}
            if uf == "SP":
                resolutions = json.loads(Path("data/alesp/identity-resolution.json").read_text())
                verified = StateAssemblyRosterRepository(connection).fetch_verified_people(
                    institution
                )
                identities = verified_subject_identities(resolutions["resolutions"], verified)
            partition = aggregate_current_roster(
                parse(payload), institution, uf, evidence, identities
            )
            if uf == "MA":
                published = AnnualDashboardRepository(
                    connection
                ).fetch_current_official_assembly_rosters(partition["year"])
                partition = preserve_dated_ma_diary(partition, published)
            store_partition(arguments.storage, partition)
            partitions.append(partition)
        if arguments.activate:
            AnnualDashboardRepository(connection).activate_partitions(partitions)
    print(
        json.dumps(
            [
                {
                    "uf": p["territory_code"],
                    "total": p["total"],
                    "canonical_matches": p["canonical_roster_matches"],
                }
                for p in partitions
            ]
        )
    )


if __name__ == "__main__":
    main()
