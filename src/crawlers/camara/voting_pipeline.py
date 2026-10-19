"""Official period files to verified daily inputs, with no SQL voting projection."""

from pathlib import Path

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import OFFICIAL_HOSTS, SOURCE
from crawlers.camara.voting_acquisition import (
    collect_identified_matters,
    collect_voting_documents,
)
from crawlers.camara.voting_configuration import VotingConfiguration, validate_voting_scope
from crawlers.camara.voting_identity import collect_identity_profiles, resolve_voting_people
from crawlers.camara.voting_propositions import discover_voting_sources
from crawlers.camara.voting_staging import PARSER_VERSION, build_daily_records
from service.voting_pipeline.runtime import official_source_acquisition
from service.voting_pipeline.source_storage import write_source_daily_input


def collect_camara_source_files(
    connection,
    storage,
    start,
    end,
    output_path,
    *,
    max_votings=25,
    max_propositions=25,
    max_identity_profile_downloads=0,
    max_pages=5,
    max_vote_rows=20000,
    identity_profiles=(),
    proposition_ids=(),
):
    configuration = VotingConfiguration(
        Path(storage).resolve(),
        max_votings=max_votings,
        max_propositions=max_propositions,
        max_identity_profiles=max_identity_profile_downloads,
        max_pages=max_pages,
        max_vote_rows=max_vote_rows,
    )
    validate_voting_scope(configuration, start, end)
    with official_source_acquisition(
        connection, configuration, SOURCE, OFFICIAL_HOSTS, CamaraAcquisition
    ) as acquisition:
        return normalize_camara_source_files(
            connection,
            acquisition,
            configuration,
            start,
            end,
            output_path,
            identity_profiles=identity_profiles,
            proposition_ids=proposition_ids,
        )


def normalize_camara_source_files(
    connection,
    acquisition,
    configuration,
    start,
    end,
    output_path,
    *,
    identity_profiles=(),
    proposition_ids=(),
):
    """Injectable processing boundary for source-contract and no-write tests."""
    selected, discovery_artifacts, discovery_complete = discover_voting_sources(
        acquisition, start, end, configuration.max_votings, proposition_ids
    )
    events = collect_voting_documents(acquisition, selected, configuration.max_vote_rows)
    for event in events:
        event["artifacts"].extend(discovery_artifacts)
    matters, matter_artifacts, matter_deferred = collect_identified_matters(
        acquisition, events, configuration.max_propositions
    )
    profiles, profile_counts = collect_identity_profiles(
        acquisition, events, configuration, supplied=identity_profiles
    )
    identities = resolve_voting_people(connection, profiles)
    rows, unresolved, description_missing = build_daily_records(
        events, identities, matters, matter_artifacts
    )
    receipts = source_receipts(
        start, end, discovery_artifacts, events, rows, unresolved, discovery_complete
    )
    dependencies = {artifact.sha256 for artifact in profiles.values()}
    dependencies.update(artifact.sha256 for artifact in matter_artifacts.values())
    dependencies.update(artifact.sha256 for event in events for artifact in event["artifacts"])
    result = write_source_daily_input(
        output_path,
        rows,
        receipts,
        parser_version=PARSER_VERSION,
        evidence_dependencies=dependencies,
    )
    return (
        result
        | profile_counts
        | {
            "identity_unresolved": unresolved,
            "description_missing": description_missing,
            "propositions_deferred": matter_deferred,
            "votings": len(events),
            "status": "partial",
            "discovery_complete": discovery_complete,
            "nominal_completeness": "not_verified_no_absence_or_modality_inferred",
            "sql_vote_writes": 0,
        }
    )


def source_receipts(start, end, artifacts, events, rows, unresolved, discovery_complete):
    return [
        {
            "source": "camara",
            "channel": "all_official_bodies",
            "starts_on": start.isoformat(),
            "ends_on": end.isoformat(),
            "artifact_sha256": artifact.sha256,
            "source_observed_at": artifact.fetched_at,
            "parser_version": PARSER_VERSION,
            "votings": len(events),
            "resolved_votes": len(rows),
            "unresolved_votes": unresolved,
            "discovery_complete": discovery_complete,
            "collection_complete": False,
            "coverage": "requested_period_not_entire_career",
        }
        for artifact in artifacts
    ]
