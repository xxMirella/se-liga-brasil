"""Opt-in official description enrichment of bounded, already registered propositions."""

from dataclasses import asdict
from functools import partial

from crawlers.senado.acquisition import SenateAcquisition
from crawlers.senado.configuration import OFFICIAL_HOSTS, SOURCE, SenateConfiguration
from crawlers.senado.legislative import bounded_process_keys, collect_process_details
from crawlers.senado.process_staging import (
    PARSER_VERSION,
    SenateProcessSummaryProjection,
    process_summary_record,
    stage_process_summary,
)
from normalization.scalars import normalize_digits
from service.ingestion.contracts import IngestionError
from service.legislative_collection.runtime import CollectionDefinition, run_official_collection

PROCESS_URL = "https://legis.senado.leg.br/dadosabertos/processo/"


def known_processes(connection, process_keys):
    urls = [PROCESS_URL + str(key) for key in process_keys]
    rows = connection.execute(
        """
        SELECT p.official_key,p.kind,p.number,p.year FROM se_liga_brasil.proposition p
        JOIN se_liga_brasil.institution i ON i.id=p.institution_id AND i.code='senado'
        WHERE p.official_key=ANY(%s)
    """,
        (urls,),
    ).fetchall()
    index = {row["official_key"].removeprefix(PROCESS_URL): row for row in rows}
    if len(index) != len(process_keys):
        raise IngestionError("SENATE_PROPOSITION_NOT_REGISTERED")
    return index


def validate_registered_process(process, registered):
    for field in ("kind", "number", "year"):
        expected, observed = registered.get(field), process.get(field)
        if expected is not None and str(expected) != str(observed):
            raise IngestionError("SENATE_REGISTERED_PROPOSITION_MISMATCH")


def ingest_process_summaries(command, configuration, acquisition, repository, *, processes):
    results, failures = [], []
    for process, artifact in collect_process_details(acquisition, processes, max_processes=1):
        validate_registered_process(process, processes[process["source_key"]])
        validated = stage_process_summary(artifact, configuration, process)
        summary = repository.ingest_validated_artifact(validated, configuration.batch_size)
        has_description = process_summary_record(process)["summary"] is not None
        if not has_description:
            failures.append({"code": "SENATE_PROCESS_SUMMARY_NOT_PUBLISHED"})
        results.append(
            asdict(summary)
            | {
                "process_key": process["source_key"],
                "artifact_sha256": artifact.sha256,
                "official_description_published": has_description,
            }
        )
    return {
        "artifacts": results,
        "failures": failures,
        "coverage": "explicit_known_processes_only_not_legislative_history",
    }


def collect_senate_process_details(connection, storage, process_keys, *, max_processes=1):
    if type(max_processes) is not int or max_processes != 1:
        raise IngestionError("SENATE_PROCESS_SUMMARY_BUDGET_MUST_BE_ONE")
    keys = bounded_process_keys((normalize_digits(key) for key in process_keys), max_processes)
    if not keys:
        raise IngestionError("SELECT_EXPLICIT_SENATE_PROCESS")
    processes = known_processes(connection, keys)
    configuration = SenateConfiguration(storage.resolve())
    definition = CollectionDefinition(
        SOURCE, PARSER_VERSION, OFFICIAL_HOSTS, SenateProcessSummaryProjection, SenateAcquisition
    )
    pipeline = partial(ingest_process_summaries, processes=processes)
    return run_official_collection(connection, configuration, definition, pipeline)
