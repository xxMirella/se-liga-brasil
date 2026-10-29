"""Normalized roll-call records shared by both chambers."""

from dataclasses import dataclass
from datetime import date

from service.party_vote_analysis.choices import Choice


@dataclass(frozen=True)
class PropositionRef:
    kind: str  # official type acronym, e.g. PEC, PL, PLV
    number: int
    year: int
    summary: str = ""  # official ementa

    @property
    def label(self) -> str:
        return f"{self.kind} {self.number}/{self.year}"


@dataclass(frozen=True)
class VotingRecord:
    chamber: str  # "camara" | "senado"
    voting_id: str
    voted_on: date
    description: str
    propositions: tuple[PropositionRef, ...]
    source_file: str


@dataclass(frozen=True)
class VoteRecord:
    chamber: str
    voting_id: str
    voted_on: date
    member_id: str
    party_at_vote: str  # acronym published with the vote, never the current affiliation
    state: str
    choice: Choice


@dataclass(frozen=True)
class OrientationRecord:
    voting_id: str
    bloc: str  # "Governo", "Oposição", "Maioria", "Minoria" or a party acronym
    orientation: str  # official label: Sim, Não, Liberado, Obstrução...
