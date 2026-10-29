"""Normalization of the Senate's annual /votacao JSON (substantive plenary roll calls)."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from service.party_vote_analysis.choices import Choice, parse_choice
from service.party_vote_analysis.contracts import PropositionRef, VoteRecord, VotingRecord
from service.party_vote_analysis.merit_selection import is_senate_main_text_vote

SECRET_BALLOT_LABEL = "votou"  # the source publishes who voted, not how (secret ballot)


def senate_voting_id(row: dict) -> str:
    return f"{row['codigoSessao']}-{row['codigoSessaoVotacao']}"


def read_substantive_votings(path: Path) -> Iterator[tuple[VotingRecord, list[VoteRecord]]]:
    for row in json.loads(path.read_text(encoding="utf-8")):
        kind = (row.get("sigla") or "").upper()
        if not row.get("votos") or row.get("votacaoSecreta") == "S":
            continue
        if not is_senate_main_text_vote(kind, row.get("descricaoVotacao") or ""):
            continue
        if not str(row.get("numero")).isdigit():
            continue  # numbers such as "1A" cannot be matched to a proposition key
        yield _normalize_row(row, kind, path.name)


def _normalize_row(row: dict, kind: str, source_file: str):
    voted_on = date.fromisoformat(row["dataSessao"])
    reference = PropositionRef(kind, int(row["numero"]), int(row["ano"]), row.get("ementa") or "")
    voting = VotingRecord(
        "senado",
        senate_voting_id(row),
        voted_on,
        row.get("descricaoVotacao") or "",
        (reference,),
        source_file,
    )
    votes = [_normalize_vote(voting, entry) for entry in row["votos"]]
    return voting, votes


def _normalize_vote(voting: VotingRecord, entry: dict) -> VoteRecord:
    label = entry["siglaVotoParlamentar"] or ""
    choice = Choice.OTHER if label.lower() == SECRET_BALLOT_LABEL else parse_choice(label)
    return VoteRecord(
        "senado",
        voting.voting_id,
        voting.voted_on,
        str(entry["codigoParlamentar"]),
        (entry.get("siglaPartidoParlamentar") or "").strip(),
        entry.get("siglaUFParlamentar") or "",
        choice,
    )
