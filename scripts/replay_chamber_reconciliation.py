"""Replay archived Chamber reconciliation without network, credentials or database writes."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from build_chamber_reconciliation_annual import build_reconciled_partitions, write_json

from service.political_dashboard_dataset.storage import encode_partition


def frozen_snapshot_identities(storage):
    identities = {}
    for path in sorted((storage / "crosswalk").glob("*.json")):
        for member in json.loads(path.read_text()):
            identifier = member["source_person_id"]
            person_id = member["person_id"]
            previous = identities.setdefault(identifier, {"person_id": person_id})
            if previous["person_id"] != person_id:
                raise ValueError("CHAMBER_FROZEN_IDENTITY_CONFLICT")
    if not identities:
        raise ValueError("CHAMBER_FROZEN_IDENTITIES_MISSING")
    return identities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-storage", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--evidence-storage", type=Path,
                        default=Path("data/camara-reconciliation-2010-2026"))
    parser.add_argument("--destination", type=Path, required=True)
    options = parser.parse_args()
    if options.destination.resolve() == options.evidence_storage.resolve():
        raise ValueError("CHAMBER_REPLAY_DESTINATION_MUST_DIFFER_FROM_SOURCE")
    if options.destination.exists() and any(options.destination.iterdir()):
        raise ValueError("CHAMBER_REPLAY_DESTINATION_MUST_BE_EMPTY")
    arguments = SimpleNamespace(storage=options.destination,
                                evidence_storage=options.evidence_storage,
                                source_storage=options.source_storage)
    expected = {row["year"]: row["sha256"] for row in json.loads(
        (options.evidence_storage / "annual-manifest.json").read_text(),
    )}
    partitions, audits = build_reconciled_partitions(
        arguments, frozen_snapshot_identities(options.evidence_storage),
    )
    replayed = {row["year"]: encode_partition(row)[1] for row in partitions}
    if replayed != expected:
        raise ValueError("CHAMBER_REPLAY_DIFFERS_FROM_VERIFIED_MANIFEST")
    write_json(options.destination / "replay-audit.json", audits)
    write_json(options.destination / "replay-validation.json", {
        "matching_partition_hashes": replayed,
        "identity_basis": "frozen_snapshot_mapping_not_new_identity_resolution",
        "network_requests": 0, "database_writes": 0,
    })
    print(json.dumps({"matching_years": len(replayed), "network_requests": 0,
                      "database_writes": 0}))


if __name__ == "__main__":
    main()
