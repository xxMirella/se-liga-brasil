"""Acquire, verify and reconcile historical synopsis events without nominal ballots."""

import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

from crawlers.alerj.configuration import OFFICIAL_HOSTS, SOURCE, CrawlerConfiguration
from crawlers.alerj.historical_acquisition import (
    AlerjHistoryAcquisition,
    CachedAlerjHistoryAcquisition,
)
from crawlers.alerj.historical_identity import verify_historical_identity
from crawlers.alerj.historical_parsing import parse_synopsis_pages
from crawlers.alerj.historical_staging import PARSER_VERSION, stage_historical_events
from crawlers.alerj.payroll import extract_pdf_text
from crawlers.senado.cached_acquisition import CachedSenateAcquisition
from crawlers.senado.configuration import SenateConfiguration
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.voting_pipeline.runtime import cached_source_acquisition, official_source_acquisition
from storage.files import hash_file, save_json


@dataclass(frozen=True)
class HistoricalConfiguration(CrawlerConfiguration):
    request_accept: str = "application/pdf,text/html,application/json;q=0.8,*/*;q=0.5"


class HistoricalProjectionWriter:
    def __init__(self, connection):
        self.writer = SqlBatchWriter(connection)

    def project_batch(self, parameters, resource_kind):
        if resource_kind != "alerj_historical_synopsis":
            raise IngestionError("ALERJ_HISTORICAL_RESOURCE_KIND_INVALID")
        self.writer.execute_statements("alerj_historical_synopsis", parameters)


def load_identity_bridge(storage, senator_code):
    if not str(senator_code).isascii() or not str(senator_code).isdigit():
        raise IngestionError("ALERJ_IDENTITY_BRIDGE_CODE_INVALID")
    acquisition = CachedSenateAcquisition(SenateConfiguration(Path(storage)))
    return acquisition.json_document(f"senador/{senator_code}.json", "senado_profile")


def collect_historical_document(acquisition, repository, person_id, identity, evidence, url):
    match = re.search(r"_(\d{4})\.pdf$", url, re.I)
    if not match or not 2000 <= int(match[1]) <= date.today().year:
        raise IngestionError("ALERJ_SYNOPSIS_DOCUMENT_YEAR_INVALID")
    artifact = acquisition.acquire(url, "alerj_historical_synopsis", ".pdf")
    text = extract_pdf_text(artifact.path)
    events, rejected = parse_synopsis_pages(
        text.split("\f"), identity["displayName"], url, int(match[1])
    )
    rows = [
        event
        | {
            "personId": person_id,
            "identityMethod": identity["identityMethod"],
            "identityEvidence": evidence,
            "documentSha256": artifact.sha256,
            "storageReference": str(artifact.path),
        }
        for event in events
    ]
    validated = stage_historical_events(
        artifact, acquisition.configuration.storage_directory, rows, rejected
    )
    result = asdict(repository.ingest_validated_artifact(validated, 500))
    return {
        "url": url,
        "sha256": artifact.sha256,
        "events": len(events),
        "rejected": len(rejected),
        "ingestion": result,
    }


def collect_alerj_history(
    connection, storage, person_id, profile_url, senator_code, urls, *, offline=False
):
    if not 1 <= len(urls) <= 10:
        raise IngestionError("ALERJ_SYNOPSIS_DOCUMENT_LIMIT")
    configuration = HistoricalConfiguration(Path(storage) / "alerj-history")
    runtime = cached_source_acquisition if offline else official_source_acquisition
    factory = CachedAlerjHistoryAcquisition if offline else AlerjHistoryAcquisition
    arguments = (
        (connection, configuration, SOURCE, factory)
        if offline
        else (connection, configuration, SOURCE, OFFICIAL_HOSTS, factory)
    )
    with runtime(*arguments) as acquisition:
        profile = acquisition.acquire(profile_url, "alerj_historical_profile")
        bridge, bridge_artifact = load_identity_bridge(storage, senator_code)
        identity = verify_historical_identity(
            connection, person_id, profile.path.read_bytes(), bridge
        )
        evidence = [
            {"url": item.resource.url, "sha256": hash_file(item.path)}
            for item in (profile, bridge_artifact)
        ]
        return reconcile_historical_documents(
            acquisition, connection, person_id, identity, evidence, urls
        )


def reconcile_historical_documents(acquisition, connection, person_id, identity, evidence, urls):
    repository = IngestionRepository(
        connection, SOURCE, HistoricalProjectionWriter(connection), parser_version=PARSER_VERSION
    )
    repository.begin_run(str(uuid4()), {"purpose": "historical_synopsis", "person_id": person_id})
    documents = []
    try:
        for url in urls:
            documents.append(
                collect_historical_document(
                    acquisition, repository, person_id, identity, evidence, url
                )
            )
        result = {
            "documents": documents,
            "coverage": "partial_official_synopsis",
            "nominal_ballots_ingested": 0,
            "person_id": person_id,
            "status": "partial",
        }
        repository.finish_run("partial", result)
        save_json(acquisition.configuration.storage_directory / "checkpoint.json", result)
        return result
    except BaseException:
        repository.finish_run("failed", {"documents": documents})
        save_json(
            acquisition.configuration.storage_directory / "checkpoint.json",
            {"documents": documents, "status": "failed", "person_id": person_id},
        )
        raise
