"""Reusable official-source lifecycle with durable cooldown and source locking."""

from dataclasses import dataclass

import httpx

from database.data_gaps import postpone_source
from service.acquisition.http_client import OfficialHttpClient
from service.crawling.acquisition import local_run_lock
from service.crawling.runs import execute_ingestion_run
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import describe_error


@dataclass(frozen=True)
class CollectionDefinition:
    source: object
    parser_version: str
    allowed_hosts: frozenset[str]
    projector_factory: object
    acquisition_factory: object


def check_source_cooldown(connection, source_code):
    row = connection.execute(
        """SELECT ceil(extract(epoch FROM cooldown_until-now()))::int AS remaining
        FROM se_liga_brasil.source_request_policy
        WHERE source_code=%s AND cooldown_until>now()""",
        (source_code,),
    ).fetchone()
    if row:
        raise IngestionError("SOURCE_COOLDOWN_ACTIVE", {"retry_after_seconds": row["remaining"]})


def run_official_collection(connection, configuration, definition, pipeline):
    check_source_cooldown(connection, definition.source.code)
    repository = IngestionRepository(
        connection,
        definition.source,
        definition.projector_factory(SqlBatchWriter(connection)),
        parser_version=definition.parser_version,
    )
    lock_directory = configuration.storage_directory / "source-locks" / definition.source.code
    try:
        with (
            local_run_lock(lock_directory),
            httpx.Client(
                timeout=configuration.request_timeout_seconds,
                headers={"Accept": "application/json", "User-Agent": "SeLigaBrasilCrawler/1.0"},
            ) as client,
        ):
            transport = OfficialHttpClient(configuration, client, definition.allowed_hosts)
            acquisition = definition.acquisition_factory(configuration, transport)
            return execute_ingestion_run(
                "history",
                configuration,
                acquisition,
                repository,
                pipeline=pipeline,
            )
    except Exception as error:
        failure = describe_error(error)
        if failure.get("status") in {403, 429, 500, 502, 503, 504}:
            postpone_source(
                connection,
                definition.source.code,
                max(3600, failure.get("retry_after_seconds", 0)),
                failure["code"],
                failure["status"],
            )
        raise
