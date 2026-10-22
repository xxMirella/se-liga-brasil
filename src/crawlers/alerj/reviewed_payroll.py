"""Ingest only payroll links explicitly approved against an immutable source."""

from uuid import uuid4

import httpx

from crawlers.alerj.acquisition import AlerjAcquisition
from crawlers.alerj.configuration import (
    OFFICIAL_HOSTS,
    PARSER_VERSION,
    SOURCE,
    CrawlerConfiguration,
)
from crawlers.alerj.pipeline import collect_shared_evidence, ingest_records
from crawlers.alerj.projection import AlerjProjectionWriter
from service.acquisition.http_client import OfficialHttpClient
from service.identity_resolution.reviewed_names import reviewed_payroll_rows
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter


def collect_reviewed_payroll(connection, storage, people, reviews):
    if not reviews:
        return {"people_linked": 0, "status": "completed"}
    configuration = CrawlerConfiguration(storage / "alerj")
    repository = IngestionRepository(
        connection, SOURCE, AlerjProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "user_reviewed_payroll_name_links"})
    try:
        with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
            acquisition = AlerjAcquisition(
                configuration, OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
            )
            _, _, payroll, document, _ = collect_shared_evidence(acquisition, people)
            if document is None:
                raise IngestionError("REVIEWED_PAYROLL_SOURCE_MISSING")
            rows = reviewed_payroll_rows(
                people, payroll, document, reviews, source_code=SOURCE.code, represented_uf="RJ"
            )
            result = {
                "people_linked": len(rows),
                "ingestion": ingest_records(repository, acquisition, document, rows),
                "status": "completed",
            }
        repository.finish_run("completed", result)
        return result
    except BaseException:
        repository.finish_run("failed", {})
        raise
