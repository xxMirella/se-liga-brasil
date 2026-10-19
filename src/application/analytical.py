"""Optional local analytical commands; existing crawlers do not import DuckDB."""

from dataclasses import asdict
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from database.analytical_export import export_person_votes, export_person_voting_timeline
from database.operations import PROJECT_ROOT, connect_database
from service.analytical_datasets import DatasetPartition, publish_person_votes, query_person_votes
from service.ingestion.contracts import IngestionError


def execute_analytical_command(arguments):
    if not arguments.years or "," in arguments.years or arguments.years == "all":
        raise IngestionError("SELECT_ONE_DATASET_YEAR")
    if arguments.source not in {"camara", "senado", "alesp", "alerj", "cmsp"}:
        raise IngestionError("SELECT_LEGISLATIVE_INSTITUTION")
    partition = DatasetPartition(arguments.source, int(arguments.years))
    directory = (arguments.dataset_directory or PROJECT_ROOT / "data/derived").resolve()
    if arguments.command == "query-dataset":
        return query_analytical_votes(arguments, directory, partition)
    publisher, exporter, parser_version = dataset_build_strategy(arguments.command)
    if arguments.input_file:
        manifest = publisher(arguments.input_file, directory, partition, parser_version)
        return asdict(manifest)
    with TemporaryDirectory() as temporary:
        input_path = Path(temporary) / "canonical.ndjson"
        with connect_database(arguments.env_file) as connection:
            exporter(connection, input_path, partition.institution_code, partition.year)
        return asdict(publisher(input_path, directory, partition, parser_version))


def query_analytical_votes(arguments, directory, partition):
    if not arguments.person_id:
        raise IngestionError("PERSON_ID_REQUIRED")
    start = (
        date.fromisoformat(arguments.start_date)
        if arguments.start_date
        else date(partition.year, 1, 1)
    )
    end = (
        date.fromisoformat(arguments.end_date)
        if arguments.end_date
        else date(partition.year, 12, 31)
    )
    rows = query_person_votes(
        directory, partition, arguments.person_id, start, end, limit=arguments.limit
    )
    return {"rows": rows, "count": len(rows), "coverage": "selected_local_partition_only"}


def dataset_build_strategy(command):
    if command == "build-voting-timeline":
        from service.analytical_datasets.public_voting_timeline import (
            publish_person_voting_timeline,
        )

        return (
            publish_person_voting_timeline,
            export_person_voting_timeline,
            "canonical-voting-timeline-v1",
        )
    return publish_person_votes, export_person_votes, "canonical-votes-v1"
