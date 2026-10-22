"""Explicit bounded historical commands; no bulk crawl is enabled by default."""

import json
from datetime import date
from uuid import UUID

from crawlers.cmsp.identity import ReviewedAuthorBinding
from crawlers.senado.voting_pipeline import collect_senate_voting_partitions
from database.operations import PROJECT_ROOT, connect_database
from service.ingestion.contracts import IngestionError
from service.legislative_collection.sources import collect_camara_history, collect_cmsp_history


def execute_historical_command(arguments):
    storage = (arguments.storage_directory or PROJECT_ROOT / "data/enrichment").resolve()
    with connect_database(arguments.env_file) as connection:
        if arguments.command == "collect-votes":
            if arguments.source != "senado" or not arguments.start_date or not arguments.end_date:
                raise IngestionError("SELECT_SENADO_AND_EXPLICIT_VOTING_DATES")
            return collect_senate_voting_partitions(
                connection,
                storage,
                date.fromisoformat(arguments.start_date),
                date.fromisoformat(arguments.end_date),
                max_partitions=arguments.max_partitions,
                max_votings=arguments.limit,
                max_identity_profile_downloads=arguments.max_identity_profiles,
                **({"local_only": True} if getattr(arguments, "local_only", False) else {}),
            )
        if arguments.source == "camara":
            people = [str(UUID(arguments.person_id))] if arguments.person_id else None
            start = date.fromisoformat(arguments.start_date) if arguments.start_date else None
            end = date.fromisoformat(arguments.end_date) if arguments.end_date else None
            if (start is None) != (end is None) or (start and start > end):
                raise IngestionError("INVALID_LEGISLATIVE_INTERVAL")
            return collect_camara_history(
                connection, storage, people, limit=arguments.limit, start=start, end=end,
                proposition_ids=tuple(filter(None, (arguments.proposition_ids or "").split(","))),
            )
        if arguments.source == "cmsp" and arguments.years and arguments.years != "all":
            bindings = read_reviewed_bindings(arguments.reviewed_identities)
            return collect_cmsp_history(
                connection,
                storage,
                [int(year) for year in arguments.years.split(",")],
                reviewed_bindings=bindings,
            )
        raise IngestionError("SELECT_SUPPORTED_HISTORICAL_SOURCE_AND_SCOPE")


def read_reviewed_bindings(path):
    if path is None:
        return ()
    if path.stat().st_size > 1024 * 1024:
        raise IngestionError("REVIEWED_IDENTITIES_FILE_LIMIT_EXCEEDED")
    return tuple(
        ReviewedAuthorBinding(
            UUID(row["person_id"]),
            row["official_author_name"],
            row["artifact_sha256"],
            row["evidence_reference"],
        )
        for row in json.loads(path.read_text())
    )
