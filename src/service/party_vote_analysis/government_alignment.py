"""Agreement of party majorities with the official government orientation (Chamber only).

The Chamber publishes the bloc leaders' orientation per roll call (Governo, Oposição, Maioria,
Minoria, parties). Agreement measures behaviour relative to the government of the day; it is
not ideology and must never be added to a left-right score (it captures fisiologismo and
coalition membership as much as preference).
"""

from collections import Counter, defaultdict
from datetime import date

from service.party_vote_analysis.choices import Choice
from service.party_vote_analysis.legislatures import government_on
from service.party_vote_analysis.party_metrics import MINIMUM_VOTERS_FOR_COHESION, Tallies

DIRECTIONAL = {"sim": Choice.YES, "não": Choice.NO, "nao": Choice.NO}
GOVERNMENT_BLOC = "governo"


def directional_orientation(label: str) -> Choice | None:
    return DIRECTIONAL.get(label.strip().lower())


def party_majority(counts: Counter) -> Choice | None:
    yes, no = counts[Choice.YES], counts[Choice.NO]
    if yes + no < MINIMUM_VOTERS_FOR_COHESION or yes == no:
        return None
    return Choice.YES if yes > no else Choice.NO


def orientation_map(orientations: list[dict]) -> dict[str, dict[str, Choice]]:
    """voting_id -> {bloc lower-case: directional orientation} ignoring Liberado/Obstrução."""
    by_voting: dict[str, dict[str, Choice]] = defaultdict(dict)
    for row in orientations:
        direction = directional_orientation(row["orientation"])
        if direction is not None:
            by_voting[row["voting_id"]][row["bloc"].strip().lower()] = direction
    return by_voting


def government_agreement(tallies: Tallies, orientations, voting_dates: dict[str, date]):
    """(party, government) -> [agreements, comparable roll calls]."""
    result: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for (voting_id, party), counts in tallies.items():
        government_direction = orientations.get(voting_id, {}).get(GOVERNMENT_BLOC)
        majority = party_majority(counts)
        government = government_on(voting_dates[voting_id])
        if government_direction is None or majority is None or government is None:
            continue
        cell = result[(party, government)]
        cell[0] += int(majority is government_direction)
        cell[1] += 1
    return result


def leader_orientation_following(tallies: Tallies, orientations) -> dict[str, list[float]]:
    """party -> [mean share of voting members who followed their own bloc leader, n roll calls]."""
    shares: dict[str, list[float]] = defaultdict(list)
    for (voting_id, party), counts in tallies.items():
        direction = orientations.get(voting_id, {}).get(party.strip().lower())
        decided = counts[Choice.YES] + counts[Choice.NO]
        if direction is None or decided < MINIMUM_VOTERS_FOR_COHESION:
            continue
        shares[party].append(counts[direction] / decided)
    return shares
