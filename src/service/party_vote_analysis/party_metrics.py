"""Party-level descriptive statistics per roll call: share of yes, Rice cohesion, non-votes."""

from collections import Counter, defaultdict
from collections.abc import Iterable

from service.party_vote_analysis.choices import Choice
from service.party_vote_analysis.contracts import VoteRecord

MINIMUM_VOTERS_FOR_COHESION = 5

Tallies = dict[tuple[str, str], Counter]


def tally_votes(votes: Iterable[VoteRecord]) -> Tallies:
    """Counts of each choice per (voting, party-at-vote). Absent members do not appear."""
    tallies: Tallies = defaultdict(Counter)
    for vote in votes:
        tallies[(vote.voting_id, vote.party_at_vote)][vote.choice] += 1
    return tallies


def rice_index(yes: int, no: int) -> float:
    """|yes - no| / (yes + no): 1 means unanimous, 0 means an even split (Rice, 1925)."""
    return abs(yes - no) / (yes + no)


def cohesion_by_party(tallies: Tallies) -> dict[str, dict]:
    grouped: dict[str, list[Counter]] = defaultdict(list)
    for (_, party), counts in tallies.items():
        grouped[party].append(counts)
    return {party: _summarize(counts_list) for party, counts_list in grouped.items()}


def _summarize(counts_list: list[Counter]) -> dict:
    decided = [
        c for c in counts_list if c[Choice.YES] + c[Choice.NO] >= MINIMUM_VOTERS_FOR_COHESION
    ]
    total_positions = sum(
        c[Choice.YES] + c[Choice.NO] + c[Choice.ABSTENTION] + c[Choice.OBSTRUCTION]
        for c in counts_list
    )
    return {
        "n_votings_with_party_votes": len(counts_list),
        "n_votings_with_cohesion": len(decided),
        "mean_yes_share": _mean([c[Choice.YES] / (c[Choice.YES] + c[Choice.NO]) for c in decided]),
        "rice_index_mean": _mean([rice_index(c[Choice.YES], c[Choice.NO]) for c in decided]),
        "obstruction_rate": _ratio(
            sum(c[Choice.OBSTRUCTION] for c in counts_list), total_positions
        ),
        "abstention_rate": _ratio(sum(c[Choice.ABSTENTION] for c in counts_list), total_positions),
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None
