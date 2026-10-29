"""Classify several parties and periods in one pass; output order is stable."""

from collections.abc import Iterable

from service.party_orientation_model.applicability import index_evidence_by_party
from service.party_orientation_model.classifier import (
    PartyPeriodClassification,
    classify_party_period,
)
from service.party_orientation_model.contracts import (
    EvidenceItem,
    PartyModelContractError,
    PartySuccession,
    Period,
    Rubric,
    normalize_party_key,
)


def parties_in_evidence(
    evidence: Iterable[EvidenceItem], successions: Iterable[PartySuccession]
) -> list[str]:
    """Display acronyms, one per political_party_id, sorted by id; successors included."""
    names = {}
    for item in evidence:
        names.setdefault(normalize_party_key(item.political_party), item.political_party)
    for succession in successions:
        for name in (succession.predecessor, succession.successor):
            names.setdefault(normalize_party_key(name), name)
    return [names[key] for key in sorted(names)]


def resolve_period(rubric: Rubric, period_id: str) -> Period:
    for period in rubric.periods:
        if period.period_id == period_id:
            return period
    parts = period_id.split("-")
    if all(part.isdigit() for part in parts) and len(parts) in (1, 2):
        start, end = int(parts[0]), int(parts[-1])
        if start <= end:
            return Period(period_id, start, end)
    raise PartyModelContractError("PERIOD_NOT_RECOGNIZED", period_id)


def classify_many(
    parties: Iterable[str],
    periods: Iterable[Period],
    evidence: tuple[EvidenceItem, ...],
    successions: tuple[PartySuccession, ...],
    rubric: Rubric,
    include_without_evidence: bool = True,
) -> list[PartyPeriodClassification]:
    period_list = sorted(periods, key=lambda period: (period.year_start, period.year_end))
    indexed = index_evidence_by_party(evidence)
    unique_parties = {normalize_party_key(name): name for name in parties}
    classifications = (
        classify_party_period(party, period, evidence, successions, rubric, evidence_index=indexed)
        for party in sorted(unique_parties.values(), key=normalize_party_key)
        for period in period_list
    )
    return [c for c in classifications if include_without_evidence or c.used_evidence]
