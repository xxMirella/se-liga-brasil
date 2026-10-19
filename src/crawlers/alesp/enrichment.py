"""Execute a source collection requested by the independent completeness service."""

from uuid import uuid4

import httpx

from crawlers.alesp.configuration import (
    ALESP_PARSER_VERSION,
    ALESP_SOURCE,
    OFFICIAL_HOSTS,
    load_configuration,
)
from crawlers.alesp.local_enrichment import collect_alesp_local_enrichment
from crawlers.alesp.projection import AlespProjectionWriter
from database.operations import PROJECT_ROOT
from service.acquisition.http_client import OfficialHttpClient
from service.crawling.alesp_pipeline import run_alesp_pipeline
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import describe_error


def collect_alesp_enrichment(connection, person_ids=None, fields=None) -> dict:
    configuration = load_configuration(PROJECT_ROOT / "config/alesp-crawler.json", {})
    repository = IngestionRepository(
        connection,
        ALESP_SOURCE,
        AlespProjectionWriter(SqlBatchWriter(connection)),
        parser_version=ALESP_PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "service_requested_state_data"})
    try:
        requested_fields = set(
            fields
            or {
                "current_salary",
                "current_public_office",
                "current_political_party",
                "political_activity",
            }
        )
        result = {
            "local_enrichment": collect_alesp_local_enrichment(
                repository, configuration.storage_directory, person_ids, requested_fields
            )
        }
        if "current_salary" in requested_fields:
            try:
                with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
                    transport = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
                    result.update(run_alesp_pipeline("run", configuration, transport, repository))
            except Exception as error:
                result["failures"] = [describe_error(error)]
        status = (
            "partial"
            if result.get("failures") or result.get("identity_unresolved")
            else "completed"
        )
        repository.finish_run(status, result)
        return result | {"status": status}
    except BaseException:
        repository.finish_run("failed", {})
        raise
