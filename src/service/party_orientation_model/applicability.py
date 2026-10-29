"""Select the evidence that may speak for a party in a period (window and sourced lineage)."""

from collections import defaultdict
from collections.abc import Iterable

from service.party_orientation_model.contracts import (
    EvidenceItem,
    ExcludedEvidence,
    PartyModelContractError,
    PartySuccession,
    Period,
    Rubric,
    ScoredEvidence,
    normalize_party_key,
    proof_rank,
)

REASON_OUTSIDE_PERIOD = "validity_window_outside_period"
REASON_AFTER_SUCCESSION = "dated_after_succession_under_predecessor_name"


def index_evidence_by_party(items: Iterable[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
    indexed = defaultdict(list)
    identifiers = set()
    for item in items:
        if item.evidence_id in identifiers:
            raise PartyModelContractError("EVIDENCE_ID_DUPLICATED", item.evidence_id)
        identifiers.add(item.evidence_id)
        indexed[normalize_party_key(item.political_party)].append(item)
    return indexed


def predecessor_cutoffs(party_key: str, successions: Iterable[PartySuccession]) -> dict[str, int]:
    """Map each (transitive) predecessor to the last year its evidence may speak for the party."""
    by_successor = defaultdict(list)
    for succession in successions:
        by_successor[normalize_party_key(succession.successor)].append(succession)
    cutoffs: dict[str, int] = {}
    pending = [(party_key, 9999)]
    while pending:
        current, limit = pending.pop()
        for succession in by_successor.get(current, ()):
            predecessor = normalize_party_key(succession.predecessor)
            year = min(limit, succession.effective_date.year)
            if predecessor == party_key or cutoffs.get(predecessor, -1) >= year:
                continue
            cutoffs[predecessor] = year
            pending.append((predecessor, year))
    return cutoffs


def temporal_factor(item: EvidenceItem, period: Period) -> float:
    """Overlap divided by the shorter span, so one-year events inside a legislature count fully."""
    overlap = min(item.year_end, period.year_end) - max(item.year_start, period.year_start) + 1
    if overlap <= 0:
        return 0.0
    shortest = min(item.year_end - item.year_start + 1, period.year_end - period.year_start + 1)
    return overlap / shortest


def orient_and_weigh(
    item: EvidenceItem, rubric: Rubric, factor: float, carried_from: str | None
) -> ScoredEvidence:
    indicator = rubric.indicators[item.indicator_id]
    weight = indicator.weight * rubric.proof_multipliers[item.proof_level] * factor
    if carried_from is not None:
        weight *= rubric.succession_multiplier
    return ScoredEvidence(
        item=item,
        oriented_stance=item.stance * indicator.direction,
        weight=weight,
        temporal_factor=factor,
        carried_from=carried_from,
    )


def select_applicable_evidence(
    political_party: str,
    period: Period,
    indexed: dict[str, list[EvidenceItem]],
    successions: Iterable[PartySuccession],
    rubric: Rubric,
) -> tuple[list[ScoredEvidence], list[ExcludedEvidence]]:
    party_key = normalize_party_key(political_party)
    cutoffs = predecessor_cutoffs(party_key, successions)
    accepted, excluded = [], []
    for source_key in sorted({party_key, *cutoffs}):
        carried_source = source_key != party_key
        for item in sorted(indexed.get(source_key, ()), key=lambda entry: entry.evidence_id):
            reason = _exclusion_reason(item, period, cutoffs.get(source_key))
            if reason:
                excluded.append(ExcludedEvidence(item.evidence_id, reason))
            else:
                factor = temporal_factor(item, period)
                accepted.append(
                    orient_and_weigh(
                        item, rubric, factor, item.political_party if carried_source else None
                    )
                )
    return accepted, excluded


def _exclusion_reason(item: EvidenceItem, period: Period, cutoff_year: int | None) -> str | None:
    if cutoff_year is not None and item.year_start > cutoff_year:
        return REASON_AFTER_SUCCESSION
    if temporal_factor(item, period) == 0:
        return REASON_OUTSIDE_PERIOD
    return None


def meets_proof_level(item: EvidenceItem, minimum_level: str) -> bool:
    return proof_rank(item.proof_level) >= proof_rank(minimum_level)
