"""Collectors attest exact source channels; unavailable domains stay pending."""

from datetime import date, timedelta
from functools import partial

from crawlers.senado.voting_pipeline import collect_senate_voting_partitions
from crawlers.senado.voting_staging import PARSER_VERSION
from service.public_career_coverage.contracts import CoverageReceipt


def senate_plenary_receipts(connection, storage, resource):
    starts_on = min(scope.starts_on for scope in resource.expected_scopes)
    ends_before = max(scope.ends_before for scope in resource.expected_scopes)
    result = collect_senate_voting_partitions(
        connection,
        storage,
        starts_on,
        ends_before - timedelta(days=1),
    )
    if not result["artifacts"]:
        return ()
    artifact = result["artifacts"][0]
    resolved = set(result["resolved_person_ids"])
    return tuple(
        CoverageReceipt(
            scope,
            date.fromisoformat(artifact["checked_on"]),
            scope.person_id in resolved,
            True,
            True,
            True,
            artifact_sha256=artifact["artifact_sha256"],
            parser_version=PARSER_VERSION,
            scope_verified=True,
        )
        for scope in resource.expected_scopes
    )


def career_collectors(connection, storage):
    # Committee votes are deliberately a separate unsupported channel.
    return {("senado", "votes", "plenary"): partial(senate_plenary_receipts, connection, storage)}
