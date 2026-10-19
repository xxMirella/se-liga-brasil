"""Explicit bounded period collection, independently from personal enrichment."""

from dataclasses import dataclass
from datetime import date

from crawlers.camara.configuration import CrawlerConfiguration
from service.ingestion.contracts import IngestionError


@dataclass(frozen=True)
class VotingConfiguration(CrawlerConfiguration):
    max_pages: int = 5
    max_votings: int = 25
    max_identity_profiles: int = 0
    max_propositions: int = 25
    max_vote_rows: int = 20000


def validate_voting_scope(configuration, start, end):
    if type(start) is not date or type(end) is not date or start > end or start.year != end.year:
        raise IngestionError("INVALID_CAMARA_VOTING_INTERVAL")
    if (end - start).days >= 31:
        raise IngestionError("CAMARA_VOTING_INTERVAL_LIMIT_EXCEEDED")
    budgets = (
        (configuration.max_votings, 1, 100),
        (configuration.max_pages, 1, 100),
        (configuration.max_identity_profiles, 0, 100),
        (configuration.max_propositions, 0, 100),
        (configuration.max_vote_rows, 1, 100000),
    )
    if any(
        type(value) is not int or not lower <= value <= upper for value, lower, upper in budgets
    ):
        raise IngestionError("INVALID_CAMARA_VOTING_BUDGET")
