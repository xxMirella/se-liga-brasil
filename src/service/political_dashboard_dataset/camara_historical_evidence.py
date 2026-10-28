"""Replay and verify source archives before projecting broader historical cohorts."""

import json

from crawlers.camara.historical_universe import register_discovered_members
from crawlers.camara.history_archives import read_verified_archive, read_verified_history
from service.political_dashboard_dataset.storage import write_atomic
from storage.files import hash_content


def load_verified_historical_universe(storage):
    universe = json.loads((storage / "camara-historical-universe.json").read_text())
    if universe["schema_version"] != "camara_historical_universe.v1":
        raise ValueError("UNSUPPORTED_CAMARA_HISTORICAL_UNIVERSE")
    prepared = {row["id"]: row for row in universe["people"]}
    actual = {}
    for evidence in universe["evidence"]:
        document = read_verified_archive(storage, evidence)
        register_discovered_members(actual, document["dados"], evidence["legislature"])
    if actual != prepared:
        raise ValueError("CAMARA_HISTORICAL_UNIVERSE_DIFFERS_FROM_SOURCE_ARCHIVES")
    return universe


def archive_evidence_manifest(directory, payload):
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hash_content(content)
    write_atomic(directory / f"{digest}.json", content.encode())
    return digest


def load_historical_evidence(storage, directory):
    universe = load_verified_historical_universe(storage)
    histories, manifests = [], {}
    for row in universe["people"]:
        identifier = row["id"]
        if not (storage / "camara-history" / f"{identifier}.json").is_file():
            continue
        history = read_verified_history(storage, identifier)
        if not history["evidence"]:
            raise ValueError("CAMARA_HISTORICAL_STATUS_HAS_NO_EVIDENCE")
        histories.append(history)
        manifests[identifier] = archive_evidence_manifest(directory, {
            "official_deputy_id": identifier, "evidence": history["evidence"],
        })
    legislatures = {}
    for identifier in range(51, 58):
        evidence = json.loads((storage / "camara-legislatures" / f"{identifier}.json").read_text())
        document = read_verified_archive(storage, evidence)
        if int(document["dados"]["id"]) != identifier:
            raise ValueError("CAMARA_HISTORICAL_LEGISLATURE_SOURCE_ID_MISMATCH")
        legislatures[identifier] = document["dados"]
    digest = archive_evidence_manifest(directory, {
        "universe_evidence": universe["evidence"], "person_evidence_manifests": manifests,
    })
    return universe, histories, legislatures, manifests, digest
