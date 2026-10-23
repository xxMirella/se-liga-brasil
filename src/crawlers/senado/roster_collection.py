"""Bounded national Senate roster acquisition and provenance-backed ingestion."""

from dataclasses import asdict, replace
from uuid import uuid4

from crawlers.senado.acquisition import SenateAcquisition
from crawlers.senado.configuration import (
    OFFICIAL_HOSTS,
    PARSER_VERSION,
    SOURCE,
    SenateConfiguration,
)
from crawlers.senado.institutional_profile import normalize_institutional_profile
from crawlers.senado.institutional_projection import SenateInstitutionalProjectionWriter
from crawlers.senado.normalization import current_members
from crawlers.senado.staging import bundle_artifacts, stage_records
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.voting_pipeline.runtime import official_source_acquisition


def acquire_national_roster_batch(connection, storage, *, limit=10, offset=0):
    if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 25 or offset < 0:
        raise IngestionError("INVALID_SENATE_ROSTER_BATCH")
    configuration = SenateConfiguration(storage.resolve())
    acquired = []
    with official_source_acquisition(
        connection, configuration, SOURCE, OFFICIAL_HOSTS, SenateAcquisition
    ) as acquisition:
        roster, roster_artifact = acquisition.json_document(
            "senador/lista/atual.json", "senado_roster"
        )
        members = current_members(roster)
        for member in members[offset : offset + limit]:
            code = member["IdentificacaoParlamentar"]["CodigoParlamentar"]
            document, artifact = acquisition.json_document(f"senador/{code}.json", "senado_profile")
            data = normalize_institutional_profile(
                document, member, roster_artifact.fetched_at[:10]
            )
            bundled = bundle_artifacts(configuration, artifact, roster_artifact)
            resource = replace(bundled.resource, kind="senado_institutional_profile")
            acquired.append((replace(bundled, resource=resource), data))
    return configuration, acquired, len(members)


def ingest_national_roster_batch(connection, configuration, acquired):
    repository = IngestionRepository(
        connection,
        SOURCE,
        SenateInstitutionalProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "national_institutional_roster"})
    summaries = []
    try:
        for artifact, data in acquired:
            validated = stage_records(artifact, configuration, [data])
            summaries.append(asdict(repository.ingest_validated_artifact(validated, 500)))
        repository.finish_run("completed", {"profiles": summaries})
    except BaseException:
        repository.finish_run("failed", {})
        raise
    return summaries
