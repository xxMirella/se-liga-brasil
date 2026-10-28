"""Archive official deputy history pages for later interval validation."""

import json

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import OFFICIAL_HOSTS, SOURCE, CrawlerConfiguration
from service.voting_pipeline.runtime import official_source_acquisition
from storage.files import hash_file, save_json


def collect_batch(
    connection, storage, members, cohort="current_roster_not_all_historical_deputies",
):
    configuration = CrawlerConfiguration(storage.resolve())
    reports = []
    with official_source_acquisition(
        connection, configuration, SOURCE, OFFICIAL_HOSTS, CamaraAcquisition
    ) as acquisition:
        for member in members:
            events, evidence = [], []
            for rows, artifact in acquisition.pages(
                f"deputados/{member['id']}/historico", "camara_history"
            ):
                events.extend(rows)
                evidence.append(
                    {
                        "url": artifact.resource.url,
                        "sha256": artifact.sha256,
                        "fetched_at": artifact.fetched_at,
                    }
                )
            for legislature in {event["idLegislatura"] for event in events}:
                document, artifact = acquisition.json_document(
                    f"legislaturas/{legislature}", "camara_legislature"
                )
                save_json(
                    storage / "camara-legislatures" / f"{legislature}.json",
                    {
                        "document": document,
                        "url": artifact.resource.url,
                        "sha256": artifact.sha256,
                        "fetched_at": artifact.fetched_at,
                    },
                )
            report = {
                "official_deputy_id": str(member["id"]),
                "events": events,
                "evidence": evidence,
                "cohort": cohort,
            }
            save_json(storage / "camara-history" / f"{member['id']}.json", report)
            reports.append({"id": str(member["id"]), "events": len(events)})
    return reports


def read_verified_history(storage, identifier):
    history = json.loads((storage / "camara-history" / f"{identifier}.json").read_text())
    events = []
    for evidence in history["evidence"]:
        document = read_verified_archive(storage, evidence)
        events.extend(document["dados"])
    if events != history["events"] or any(str(event["id"]) != identifier for event in events):
        raise ValueError("CAMARA_PREPARED_HISTORY_DIFFERS_FROM_ARCHIVE")
    return history


def read_verified_archive(storage, evidence):
    path = storage / "archives" / f"{evidence['sha256']}.json"
    if hash_file(path) != evidence["sha256"]:
        raise ValueError("CAMARA_HISTORY_ARCHIVE_HASH_MISMATCH")
    return json.loads(path.read_bytes())
