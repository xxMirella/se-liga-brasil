"""ALESP CLI composition; domain adapters remain independent of the entry point."""

import httpx

from crawlers.alesp.configuration import (
    ALESP_PARSER_VERSION,
    ALESP_SOURCE,
    OFFICIAL_HOSTS,
    load_configuration,
)
from crawlers.alesp.projection import AlespProjectionWriter
from database.operations import PROJECT_ROOT, connect_database
from service.acquisition.http_client import OfficialHttpClient
from service.crawling.alesp_pipeline import run_alesp_pipeline
from service.crawling.runs import execute_ingestion_run
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import emit_event


def load_alesp_configuration(arguments):
    if arguments.ufs or arguments.office_codes:
        raise IngestionError("INVALID_CRAWLER_SCOPE")
    years = (
        None
        if arguments.years is None
        else (
            [] if arguments.years == "all" else [int(value) for value in arguments.years.split(",")]
        )
    )
    return load_configuration(
        arguments.config or PROJECT_ROOT / "config/alesp-crawler.json",
        {
            "years": years,
            "months": arguments.months.split(",") if arguments.months else None,
            "kinds": arguments.kinds.split(",") if arguments.kinds else None,
            "storage_directory": str(arguments.storage_directory)
            if arguments.storage_directory
            else None,
        },
    )


def execute_alesp_command(arguments) -> dict:
    configuration = load_alesp_configuration(arguments)
    emit_event(
        "start",
        command=arguments.command,
        years=configuration.years or "all",
        ufs=("SP",),
        kinds=configuration.kinds,
    )
    with httpx.Client(
        timeout=configuration.request_timeout_seconds,
        headers={"User-Agent": "SeLigaBrasilCrawler/1.0"},
    ) as client:
        transport = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
        if arguments.command not in {"run", "ingest", "resolve-identities"}:
            return run_alesp_pipeline(arguments.command, configuration, transport)
        with connect_database(arguments.env_file) as connection:
            repository = IngestionRepository(
                connection,
                ALESP_SOURCE,
                AlespProjectionWriter(SqlBatchWriter(connection)),
                progress=emit_event,
                parser_version=ALESP_PARSER_VERSION,
            )
            return execute_ingestion_run(
                arguments.command, configuration, transport, repository, pipeline=run_alesp_pipeline
            )
