"""Scalar roll-call choices. Domain validation only: no network, no database."""

from enum import StrEnum


class Choice(StrEnum):
    YES = "sim"
    NO = "nao"
    ABSTENTION = "abstencao"
    OBSTRUCTION = "obstrucao"
    PRESENT_NO_VOTE = "presente_sem_voto"
    PRESIDING = "presidencia"
    OTHER = "outro"


CHAMBER_LABELS = {
    "sim": Choice.YES,
    "nao": Choice.NO,
    "abstencao": Choice.ABSTENTION,
    "obstrucao": Choice.OBSTRUCTION,
    "artigo 17": Choice.PRESIDING,
    "presidente": Choice.PRESIDING,
    "p-nrv": Choice.PRESENT_NO_VOTE,
    "p-ocorrencia": Choice.PRESENT_NO_VOTE,
}


def _fold(label: str) -> str:
    folded = label.strip().lower()
    for accented, plain in (("ã", "a"), ("ç", "c"), ("õ", "o"), ("á", "a"), ("é", "e")):
        folded = folded.replace(accented, plain)
    return folded


def parse_choice(label: str) -> Choice:
    """Map an official vote label to a choice. Unknown labels stay explicit as OTHER."""
    return CHAMBER_LABELS.get(_fold(label), Choice.OTHER)


def scalar_value(choice: Choice) -> int | None:
    """+1 yes, -1 no, None for every state that is not a yes/no position."""
    if choice is Choice.YES:
        return 1
    if choice is Choice.NO:
        return -1
    return None
