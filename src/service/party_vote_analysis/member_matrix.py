"""Member-affiliation x roll-call matrix from a vote stream.

A row is a (member, party-at-the-time-of-the-vote) pair, so a member who changes party yields
one row per party, each estimated only from votes cast under that party.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from service.party_vote_analysis.choices import scalar_value
from service.party_vote_analysis.contracts import VoteRecord


@dataclass(frozen=True)
class VoteMatrix:
    values: np.ndarray  # +1 / -1 / nan
    row_keys: list[tuple[str, str]]  # (member_id, party_at_vote)
    voting_ids: list[str]

    @property
    def parties(self) -> np.ndarray:
        return np.array([party for _, party in self.row_keys])


def build_matrix(votes: Iterable[VoteRecord], minimum_votes_per_row: int) -> VoteMatrix:
    row_index: dict[tuple[str, str], int] = {}
    column_index: dict[str, int] = {}
    cells: list[tuple[int, int, int]] = []
    for vote in votes:
        value = scalar_value(vote.choice)
        if value is None:
            continue
        row = row_index.setdefault((vote.member_id, vote.party_at_vote), len(row_index))
        column = column_index.setdefault(vote.voting_id, len(column_index))
        cells.append((row, column, value))
    return _assemble(row_index, column_index, cells, minimum_votes_per_row)


def _assemble(row_index, column_index, cells, minimum_votes_per_row) -> VoteMatrix:
    values = np.full((len(row_index), len(column_index)), np.nan, dtype=np.float32)
    rows, columns, entries = (
        (np.array(part) for part in zip(*cells, strict=True))
        if cells
        else (np.array([], int), np.array([], int), np.array([], int))
    )
    values[rows, columns] = entries
    keep = np.flatnonzero((~np.isnan(values)).sum(axis=1) >= minimum_votes_per_row)
    keys = list(row_index)
    return VoteMatrix(values[keep], [keys[i] for i in keep], list(column_index))
