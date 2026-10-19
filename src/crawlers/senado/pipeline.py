"""Collect verified Senate profiles; unsupported domains remain explicit."""

from dataclasses import asdict
from uuid import uuid4

import httpx

from crawlers.senado.acquisition import SenateAcquisition
from crawlers.senado.configuration import (
    OFFICIAL_HOSTS,
    PARSER_VERSION,
    SOURCE,
    SenateConfiguration,
)
from crawlers.senado.normalization import current_members, normalize_profile
from crawlers.senado.projection import SenateProjectionWriter
from crawlers.senado.staging import bundle_artifacts, stage_records
from database.enrichment import match_official_person
from normalization.identity import normalize_person_name
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import describe_error

SUPPORTED_FIELDS = frozenset({"current_public_office", "current_political_party"})


def index_members(members):
    index = {}
    for member in members:
        name = member["IdentificacaoParlamentar"]["NomeCompletoParlamentar"]
        index.setdefault(normalize_person_name(name), []).append(member)
    return index


def select_member(candidate, index):
    names = [candidate.get("civil_name"), *(candidate.get("civil_names") or [])]
    matches = {}
    for name in names:
        if name:
            for member in index.get(normalize_person_name(name), []):
                code = member["IdentificacaoParlamentar"]["CodigoParlamentar"]
                matches[code] = member
    return next(iter(matches.values())) if len(matches) == 1 else None


def collect_profiles(repository, acquisition, people):
    roster, roster_artifact = acquisition.json_document("senador/lista/atual.json", "senado_roster")
    index = index_members(current_members(roster))
    results, failures, unmatched, deferred = [], [], [], []
    for position, candidate in enumerate(people):
        member = select_member(candidate, index)
        if member is None:
            unmatched.append(candidate["person_id"])
            continue
        if len(results) + len(failures) >= acquisition.configuration.max_people:
            deferred.append(candidate["person_id"])
            continue
        try:
            results.append(
                collect_profile(repository, acquisition, candidate, member, roster_artifact)
            )
        except Exception as error:
            failures.append({"person_id": candidate["person_id"], **describe_error(error)})
            if failures[-1].get("status") in {403, 429, 500, 502, 503, 504}:
                deferred.extend(row["person_id"] for row in people[position + 1 :])
                break
    return {
        "people": results,
        "failures": failures,
        "unmatched_person_ids": unmatched,
        "deferred_person_ids": deferred,
        "deferred": len(deferred),
    }


def collect_profile(repository, acquisition, candidate, member, roster_artifact):
    code = member["IdentificacaoParlamentar"]["CodigoParlamentar"]
    document, artifact = acquisition.json_document(f"senador/{code}.json", "senado_profile")
    profile = document["DetalheParlamentar"]["Parlamentar"]
    evidence = {
        "nomeCivil": profile["IdentificacaoParlamentar"]["NomeCompletoParlamentar"],
        "dataNascimento": profile["DadosBasicosParlamentar"]["DataNascimento"],
    }
    method = match_official_person(repository.connection, evidence, candidate["person_id"])
    observed = roster_artifact.fetched_at[:10]
    data = normalize_profile(profile, member, candidate["person_id"], method, observed)
    artifact = bundle_artifacts(acquisition.configuration, artifact, roster_artifact)
    data["evidence"] = [
        {"url": item.resource.url, "sha256": item.sha256} for item in (roster_artifact, artifact)
    ]
    validated = stage_records(artifact, acquisition.configuration, [data])
    return {
        "person_id": candidate["person_id"],
        **asdict(
            repository.ingest_validated_artifact(validated, acquisition.configuration.batch_size)
        ),
    }


def collect_senado_enrichment(connection, storage, people, fields=None):
    requested = set(fields) if fields is not None else set(SUPPORTED_FIELDS)
    unsupported = sorted(requested - SUPPORTED_FIELDS)
    if not requested.intersection(SUPPORTED_FIELDS):
        return {"people": [], "failures": [], "unsupported_fields": unsupported}
    configuration = SenateConfiguration(storage.resolve())
    repository = IngestionRepository(
        connection,
        SOURCE,
        SenateProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "orchestrated_personal_enrichment"})
    try:
        with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
            acquisition = SenateAcquisition(
                configuration, OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
            )
            result = collect_profiles(repository, acquisition, people)
        result["unsupported_fields"] = unsupported
        repository.finish_run(
            "partial" if result["failures"] or unsupported else "completed", result
        )
        return result
    except BaseException:
        repository.finish_run("failed", {})
        raise
