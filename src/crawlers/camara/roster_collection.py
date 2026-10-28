"""Bounded national roster batches preserve personal identity and shared source cooldown."""

from dataclasses import asdict, replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import OFFICIAL_HOSTS, SOURCE, CrawlerConfiguration
from crawlers.camara.institutional_profile import normalize_institutional_profile
from crawlers.camara.institutional_projection import CamaraInstitutionalProjectionWriter
from crawlers.camara.institutional_staging import PARSER_VERSION, stage_institutional_profiles
from crawlers.camara.pipeline import bundle_profile_artifacts
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.voting_pipeline.runtime import official_source_acquisition
from storage.files import hash_content


def acquire_national_roster_batch(connection, storage, *, limit=25, offset=0):
    if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 25 or offset < 0:
        raise IngestionError("INVALID_CAMARA_ROSTER_BATCH")
    configuration = CrawlerConfiguration(storage.resolve())
    acquired = []
    with official_source_acquisition(
        connection, configuration, SOURCE, OFFICIAL_HOSTS, CamaraAcquisition
    ) as acquisition:
        members, roster_artifacts = [], []
        for rows, artifact in acquisition.pages("deputados?itens=100", "camara_roster"):
            members.extend(rows)
            roster_artifacts.append(artifact)
        members.sort(key=lambda row: int(row["id"]))
        for member in members[offset : offset + limit]:
            document, artifact = acquisition.json_document(
                f"deputados/{member['id']}", "camara_profile"
            )
            observed_on = (
                datetime.fromisoformat(artifact.fetched_at)
                .astimezone(ZoneInfo("America/Belem"))
                .date()
                .isoformat()
            )
            data = normalize_institutional_profile(document, member, observed_on)
            data["evidence"] = [
                {"url": item.resource.url, "sha256": item.sha256}
                for item in [artifact, *roster_artifacts]
            ]
            bundle = bundle_profile_artifacts(acquisition, [artifact, *roster_artifacts])
            resource = replace(bundle.resource, kind="camara_institutional_profile")
            acquired.append((replace(bundle, resource=resource), data, document))
    return configuration, acquired, len(members)


def ingest_national_roster_batch(connection, configuration, acquired):
    repository = IngestionRepository(
        connection,
        SOURCE,
        CamaraInstitutionalProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "national_institutional_roster"})
    summaries = []
    try:
        if acquired:
            artifact = bundle_profile_artifacts(
                CamaraAcquisition(configuration, None), [item[0] for item in acquired]
            )
            batch_key = hash_content([item[1]["officialDeputyCode"] for item in acquired])
            artifact = replace(
                artifact,
                resource=replace(artifact.resource, resource_id="camara-roster-batch-" + batch_key),
            )
            validated = stage_institutional_profiles(
                artifact, configuration, [(data, document) for _, data, document in acquired]
            )
            summaries.append(asdict(repository.ingest_validated_artifact(validated, 500)))
        repository.finish_run("completed", {"profiles": summaries})
    except BaseException:
        repository.finish_run("failed", {})
        raise
    return summaries
