"""Streaming normalization of the Chamber's annual roll-call CSV files (plenary only)."""

import csv
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from service.party_vote_analysis.choices import parse_choice
from service.party_vote_analysis.contracts import (
    OrientationRecord,
    PropositionRef,
    VoteRecord,
    VotingRecord,
)
from service.party_vote_analysis.merit_selection import is_camara_main_text_vote

csv.field_size_limit(10**9)
PLENARY = "PLEN"


def read_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        yield from csv.DictReader(source, delimiter=";")


def read_propositions(path: Path) -> dict[str, list[PropositionRef]]:
    by_voting: dict[str, list[PropositionRef]] = {}
    for row in read_rows(path):
        try:
            reference = PropositionRef(
                row["proposicao_siglaTipo"],
                int(row["proposicao_numero"]),
                int(row["proposicao_ano"]),
                row["proposicao_ementa"],
            )
        except ValueError:
            continue
        by_voting.setdefault(row["idVotacao"], []).append(reference)
    return by_voting


def plenary_main_text_votings(votings_path: Path, propositions_path: Path):
    """Plenary roll calls that approve or reject a principal text, by voting id."""
    propositions = read_propositions(propositions_path)
    selected: dict[str, VotingRecord] = {}
    for row in read_rows(votings_path):
        if row["siglaOrgao"] != PLENARY or not is_camara_main_text_vote(row["descricao"]):
            continue
        selected[row["id"]] = VotingRecord(
            "camara",
            row["id"],
            date.fromisoformat(row["data"]),
            row["descricao"],
            tuple(propositions.get(row["id"], ())),
            votings_path.name,
        )
    return selected


def stream_votes(votes_path: Path, votings: dict[str, VotingRecord]) -> Iterator[VoteRecord]:
    for row in read_rows(votes_path):
        voting = votings.get(row["idVotacao"])
        if voting is None:
            continue
        yield VoteRecord(
            "camara",
            voting.voting_id,
            voting.voted_on,
            row["deputado_id"],
            row["deputado_siglaPartido"].strip(),
            row["deputado_siglaUf"],
            parse_choice(row["voto"]),
        )


def stream_orientations(path: Path, voting_ids: set[str]) -> Iterator[OrientationRecord]:
    for row in read_rows(path):
        if row["idVotacao"] in voting_ids and row["siglaOrgao"] == PLENARY:
            yield OrientationRecord(row["idVotacao"], row["siglaBancada"], row["orientacao"])
