"""Python entry point; no scheduler or external writes are implicit."""

import argparse
import json
from pathlib import Path

import httpx

from code_quality.system_design import review_project
from crawlers.tse.configuration import TSE_SOURCE, load_configuration
from crawlers.tse.http_client import OfficialHttpClient
from crawlers.tse.projection import TseProjectionWriter
from database.operations import (
    PROJECT_ROOT,
    apply_ingestion_schema,
    connect_database,
    verify_schema,
)
from service.crawling.runs import execute_ingestion_run
from service.crawling.tse_pipeline import run_pipeline
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import describe_error, emit_event
from service.observability.run_reporter import RunReporter


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawlers modulares de fontes oficiais")
    parser.add_argument(
        "--source",
        choices=("tse", "alesp", "camara", "alerj", "senado", "tse_filiation", "cmsp"),
        default="tse",
    )
    parser.add_argument("--months", help="Competências ALESP YYYY-MM separadas por vírgula")
    parser.add_argument(
        "command",
        choices=(
            "discover",
            "download",
            "validate",
            "ingest",
            "run",
            "db-migrate",
            "db-verify",
            "review",
            "resolve-identities",
            "audit-completeness",
            "enrich",
            "dispatch",
            "purge-gaps",
            "collect-history",
            "collect-attendance",
            "collect-session-presence",
            "collect-votes",
            "build-dataset",
            "build-voting-timeline",
            "query-dataset",
            "serve-public-api",
            "build-static-site",
            "configure-voting-schedule",
            "run-voting-pipeline",
            "voting-worker",
        ),
    )
    add_execution_arguments(parser)
    add_historical_arguments(parser)
    return parser


def add_execution_arguments(parser):
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--fields", help="Campos de completude separados por vírgula")
    parser.add_argument("--person-id", help="UUID interno para auditar ou enriquecer uma pessoa")
    parser.add_argument(
        "--years", help="Anos separados por vírgula; 'all' varre o catálogo histórico"
    )
    parser.add_argument("--ufs", help="UFs separadas por vírgula; 'all' inclui todo o Brasil")
    parser.add_argument("--kinds", help="Tipos separados por vírgula")
    parser.add_argument("--office-codes", help="Cargos TSE: 5 senador, 6 federal, 7 estadual")
    parser.add_argument("--storage-directory", type=Path)


def add_historical_arguments(parser):
    parser.add_argument("--start-date", help="Data inicial inclusiva YYYY-MM-DD")
    parser.add_argument("--end-date", help="Data final inclusiva YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--max-partitions", type=int, default=1)
    parser.add_argument(
        "--max-identity-profiles",
        type=int,
        default=0,
        help="Perfis oficiais adicionais para votos do Senado (0 desativa, máximo 100)",
    )
    parser.add_argument(
        "--proposition-ids", help="IDs de documentos da Câmara, separados por vírgula"
    )
    parser.add_argument("--reviewed-identities", type=Path)
    parser.add_argument("--dataset-directory", type=Path)
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--include-career", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8779)
    parser.add_argument("--output-directory", type=Path, default=Path("dist/public"))
    parser.add_argument("--backend-origin", help="Origem HTTPS pública da pesquisa e dos perfis")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=4)
    parser.add_argument("--poll-seconds", type=int, default=30)


def parse_scope_overrides(arguments) -> dict:
    years = None
    if arguments.years is not None:
        years = (
            [] if arguments.years == "all" else [int(year) for year in arguments.years.split(",")]
        )
    return {
        "years": years,
        "ufs": []
        if arguments.ufs == "all"
        else arguments.ufs.split(",")
        if arguments.ufs
        else None,
        "kinds": arguments.kinds.split(",") if arguments.kinds else None,
        "office_codes": arguments.office_codes.split(",") if arguments.office_codes else None,
        "storage_directory": str(arguments.storage_directory)
        if arguments.storage_directory
        else None,
    }


def execute_database_command(arguments) -> dict:
    with connect_database(arguments.env_file) as connection:
        if arguments.command == "db-migrate":
            applied = apply_ingestion_schema(connection)
            return {"applied": applied, **verify_schema(connection)}
        return verify_schema(connection)


def execute_crawler_command(arguments) -> dict:
    configuration = load_configuration(
        arguments.config or PROJECT_ROOT / "config/tse-crawler.json",
        parse_scope_overrides(arguments),
    )
    emit_event(
        "start",
        command=arguments.command,
        years=configuration.years or "all",
        ufs=configuration.ufs or "all",
        kinds=configuration.kinds,
    )
    with httpx.Client(
        timeout=configuration.request_timeout_seconds,
        headers={"User-Agent": "SeLigaBrasilCrawler/1.0"},
    ) as client:
        transport = OfficialHttpClient(configuration, client)
        if arguments.command not in {"ingest", "run"}:
            return run_pipeline(arguments.command, configuration, transport)
        with connect_database(arguments.env_file) as connection:
            repository = IngestionRepository(
                connection,
                TSE_SOURCE,
                TseProjectionWriter(SqlBatchWriter(connection)),
                progress=emit_event,
            )
            return execute_ingestion_run(
                arguments.command, configuration, transport, repository, pipeline=run_pipeline
            )


def execute_command(arguments) -> dict:
    service_result = execute_data_service_command(arguments)
    if service_result is not None:
        return service_result
    if arguments.command == "review":
        return {"findings": review_project(PROJECT_ROOT)}
    if arguments.command.startswith("db-"):
        return execute_database_command(arguments)
    if arguments.command in {"audit-completeness", "enrich", "dispatch", "purge-gaps"}:
        from application.enrichment import execute_enrichment_command

        return execute_enrichment_command(arguments)
    if arguments.source in {"camara", "alerj", "senado", "tse_filiation"}:
        raise IngestionError("USE_ENRICHMENT_SERVICE_FOR_SOURCE")
    if arguments.source == "alesp":
        from application.alesp import execute_alesp_command

        return execute_alesp_command(arguments)
    if arguments.command == "resolve-identities" or arguments.months:
        raise IngestionError("INVALID_CRAWLER_SCOPE")
    return execute_crawler_command(arguments)


def main() -> int:
    parser = create_argument_parser()
    arguments = parser.parse_args()
    if arguments.command in {
        "discover",
        "download",
        "validate",
        "ingest",
        "run",
        "resolve-identities",
        "audit-completeness",
        "enrich",
        "dispatch",
        "purge-gaps",
    }:
        storage = resolve_report_storage(arguments)
        with RunReporter(storage.resolve()) as reporter:
            return execute_reported_command(arguments, reporter)
    return execute_reported_command(arguments)


def resolve_report_storage(arguments) -> Path:
    try:
        if arguments.command in {"enrich", "audit-completeness", "dispatch", "purge-gaps"}:
            return arguments.storage_directory or PROJECT_ROOT / "data/enrichment"
        if arguments.source == "alesp":
            from application.alesp import load_alesp_configuration

            return load_alesp_configuration(arguments).storage_directory
        configuration = load_configuration(
            arguments.config or PROJECT_ROOT / "config/tse-crawler.json",
            parse_scope_overrides(arguments),
        )
        return configuration.storage_directory
    except (IngestionError, OSError, ValueError, KeyError, TypeError):
        return arguments.storage_directory or PROJECT_ROOT / "data/tse"


def execute_reported_command(arguments, reporter=None) -> int:
    try:
        result = execute_command(arguments)
    except Exception as error:
        emit_event("failed", command=arguments.command, status="failed", **describe_error(error))
        return 1
    except KeyboardInterrupt:
        emit_event(
            "failed",
            status="interrupted",
            code="USER_INTERRUPTED",
            message="Execução interrompida pelo usuário.",
        )
        return 130
    if reporter:
        result |= {
            "rejected_files": len(reporter.rejected_files),
            "rejection_log": str(reporter.log_path),
            "events_log": str(reporter.events_path),
        }
        result.setdefault(
            "status",
            "partial" if result.get("failures") or reporter.rejected_files else "completed",
        )
        emit_event("finished", **result)
    else:
        print(json.dumps(result, ensure_ascii=False, default=str))
    if (
        result.get("findings")
        or result.get("failures")
        or result.get("status") == "partial"
        or result.get("rejected_files")
    ):
        return 1
    return 0


def execute_data_service_command(arguments):
    if arguments.command == "collect-session-presence":
        from application.session_presence import execute_session_presence_command

        return execute_session_presence_command(arguments)
    if arguments.command == "collect-attendance":
        from application.attendance import execute_attendance_command

        return execute_attendance_command(arguments)
    if arguments.command == "build-static-site":
        from service.static_publication.build import build_civic_site

        return build_civic_site(arguments.output_directory, backend_origin=arguments.backend_origin)
    if arguments.command in {"configure-voting-schedule", "run-voting-pipeline", "voting-worker"}:
        from application.voting import execute_voting_command

        return execute_voting_command(arguments)
    if arguments.command == "serve-public-api":
        from application.public_api import execute_public_api_command

        return execute_public_api_command(arguments)
    if arguments.command in {"collect-history", "collect-votes"}:
        from application.legislative import execute_historical_command

        return execute_historical_command(arguments)
    if arguments.command in {"build-dataset", "query-dataset", "build-voting-timeline"}:
        from application.analytical import execute_analytical_command

        return execute_analytical_command(arguments)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
