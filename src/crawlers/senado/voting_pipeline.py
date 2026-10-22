"""Bounded voting ingestion with optional deduplicated personal-evidence acquisition."""

from dataclasses import asdict
from datetime import timedelta
from functools import partial
from itertools import islice
from urllib.parse import urlencode

from crawlers.senado.acquisition import SenateAcquisition
from crawlers.senado.configuration import OFFICIAL_HOSTS, SOURCE, SenateConfiguration
from crawlers.senado.legislative_voting import normalize_voting_record, resolve_voting_individuals
from crawlers.senado.voting_identity import cached_identity_profiles, resolve_profile_identities
from crawlers.senado.voting_profile_acquisition import (
    IdentityProfileAcquisition,
    validate_identity_profile_budget,
)
from crawlers.senado.voting_staging import (
    PARSER_VERSION,
    SenateVotingProjection,
    stage_voting_records,
)
from normalization.periods import month_intervals
from service.ingestion.contracts import IngestionError
from service.legislative_collection.runtime import (
    CollectionDefinition,
    run_cached_collection,
    run_official_collection,
)
from storage.files import hash_content, load_json


def monthly_partitions(start, end, maximum=1):
    if start > end or not 1 <= maximum <= 24:
        raise IngestionError("INVALID_SENATE_VOTING_SCOPE")
    intervals = list(islice(month_intervals(start, end + timedelta(days=1)), maximum + 1))
    if len(intervals) > maximum:
        raise IngestionError("SENATE_VOTING_PARTITION_LIMIT_EXCEEDED")
    return [(lower, upper - timedelta(days=1)) for lower, upper in intervals]


def ingest_voting_partitions(
    command,
    configuration,
    acquisition,
    repository,
    *,
    partitions,
    profile_index,
    maximum,
    profile_acquisition,
):
    results, seen, unresolved = [], {}, 0
    for start, end in partitions:
        query = urlencode({"dataInicio": start.isoformat(), "dataFim": end.isoformat(), "v": 2})
        payload, artifact = acquisition.json_document("votacao.json?" + query, "senado_votings")
        rows = select_unique_votings(payload, seen, start, end, maximum)
        profile_acquisition.extend_resolved_index(
            repository.connection, acquisition, rows, profile_index
        )
        votings = [normalize_voting_record(row) for row in rows]
        votes, missing = resolve_voting_individuals(rows, profile_index)
        unresolved += missing
        staged = stage_voting_records(artifact, configuration, votings, votes)
        summary = repository.ingest_validated_artifact(staged, configuration.batch_size)
        manifest_path = (
            configuration.storage_directory
            / "manifests"
            / (artifact.resource.resource_id + ".json")
        )
        checked_at = load_json(manifest_path, {}).get("checked_at", artifact.fetched_at)
        results.append(
            asdict(summary)
            | {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "artifact_sha256": artifact.sha256,
                "votings": len(votings),
                "resolved_votes": len(votes),
                "unresolved_votes": missing,
                "checked_on": checked_at[:10],
            }
        )
    return profile_acquisition.summary() | {
        "artifacts": results,
        "failures": [],
        "identity_unresolved": unresolved,
        "coverage": "requested_source_partitions_only_not_entire_public_career",
        "resolved_person_ids": sorted({match[0] for match in profile_index.values()}),
    }


def select_unique_votings(payload, seen, start, end, maximum):
    if not isinstance(payload, list):
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    selected = []
    for row in payload:
        normalized = normalize_voting_record(row)
        if not start.isoformat() <= normalized["occurred_on"] <= end.isoformat():
            raise IngestionError("SENATE_VOTING_OUTSIDE_PARTITION")
        key, digest = normalized["source_key"], hash_content(normalized)
        if key in seen:
            if seen[key] != digest:
                raise IngestionError("SENATE_VOTING_SNAPSHOT_CONFLICT")
            continue
        if len(seen) >= maximum:
            raise IngestionError("SENATE_VOTING_RECORD_LIMIT_EXCEEDED")
        seen[key] = digest
        selected.append(row)
    return selected


def collect_senate_voting_partitions(
    connection,
    storage,
    start,
    end,
    *,
    identity_profiles=None,
    max_partitions=1,
    max_votings=1000,
    max_identity_profile_downloads=0,
    local_only=False,
):
    validate_identity_profile_budget(max_identity_profile_downloads)
    if local_only and max_identity_profile_downloads:
        raise IngestionError("OFFLINE_VOTING_CANNOT_DOWNLOAD_IDENTITY_PROFILES")
    partitions = monthly_partitions(start, end, max_partitions)
    if not 1 <= max_votings <= 10000:
        raise IngestionError("SENATE_VOTING_RECORD_LIMIT_EXCEEDED")
    configuration = SenateConfiguration(storage.resolve())
    profiles = (
        cached_identity_profiles(storage) if identity_profiles is None else list(identity_profiles)
    )
    profile_index = resolve_profile_identities(connection, profiles)
    profile_acquisition = IdentityProfileAcquisition(max_identity_profile_downloads)
    profile_acquisition.mark_cached_profiles(profiles, configuration)
    definition = CollectionDefinition(
        SOURCE,
        PARSER_VERSION,
        OFFICIAL_HOSTS,
        SenateVotingProjection,
        SenateAcquisition,
    )
    pipeline = partial(
        ingest_voting_partitions,
        partitions=partitions,
        profile_index=profile_index,
        maximum=max_votings,
        profile_acquisition=profile_acquisition,
    )
    if local_only:
        from crawlers.senado.cached_acquisition import CachedSenateAcquisition

        return run_cached_collection(
            connection, configuration, definition, pipeline, CachedSenateAcquisition(configuration)
        )
    return run_official_collection(connection, configuration, definition, pipeline)
