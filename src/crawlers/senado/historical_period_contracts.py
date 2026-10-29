"""Typed records for the 02/10/1992-01/01/1995 Senate load; no I/O, no database."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

LOAD_NAME = "senate_history_1992_1994"
WINDOW_STARTS_ON = date(1992, 10, 2)
WINDOW_ENDS_BEFORE = date(1995, 1, 1)
AFFILIATION_SCOPE = "institution:senado:historical_affiliations"
SENATE_PARTY_CODE_PREFIX = "senado:party:"
NO_PARTY_SENATE_CODE = "163"


@dataclass(frozen=True)
class ArchivedDocument:
    """One archived official API response, identified by the SHA-256 of its original bytes."""

    kind: str
    senator_id: str | None
    url: str
    sha256: str
    fetched_at: datetime
    archive_path: str
    payload: dict = field(compare=False, hash=False)

    @property
    def fetched_on(self) -> date:
        return self.fetched_at.astimezone(UTC).date()

    @property
    def external_key(self) -> str:
        subject = f"senator:{self.senator_id}" if self.senator_id else "catalog"
        return f"{LOAD_NAME}:{subject}:{self.kind}"


@dataclass(frozen=True)
class SenatorIdentity:
    senator_id: str
    civil_name: str
    display_name: str
    birth_date: date
    document: ArchivedDocument


@dataclass(frozen=True)
class SenateParty:
    senate_party_code: str
    abbreviation: str
    name: str
    created_on: date | None
    extinguished_on: date | None
    document: ArchivedDocument

    @property
    def code(self) -> str:
        return SENATE_PARTY_CODE_PREFIX + self.senate_party_code


@dataclass(frozen=True)
class SenateTerm:
    senator_id: str
    mandate_code: str | None
    represented_uf: str
    capacity: str | None
    legislature_key: str
    starts_on: date
    ends_before: date
    document: ArchivedDocument


@dataclass(frozen=True)
class SenateExercise:
    senator_id: str
    legislature_key: str
    starts_on: date
    ends_before: date | None
    capacity: str | None
    departure_cause_code: str | None
    departure_cause: str | None
    document: ArchivedDocument


@dataclass(frozen=True)
class SenateAffiliation:
    """Parliamentary registration published by the Senate; not a civil membership record."""

    senator_id: str
    senate_party_code: str
    abbreviation: str
    starts_on: date
    ends_before: date | None
    document: ArchivedDocument
    raw_element: dict = field(compare=False, hash=False)

    @property
    def is_without_party(self) -> bool:
        return self.senate_party_code == NO_PARTY_SENATE_CODE


@dataclass(frozen=True)
class YearOnlyAffiliationClaim:
    """Affiliation published with year precision only; no day is invented for it."""

    senator_id: str
    senate_party_code: str | None
    party_abbreviation: str | None
    year_from: int | None
    year_until: int | None
    document: ArchivedDocument
    raw_element: dict = field(compare=False, hash=False)


@dataclass(frozen=True)
class PendingItem:
    """A fact that is deliberately not ingested, with the reason and where it came from."""

    code: str
    senator_id: str | None
    detail: str
    withheld_scope: str = "fact"


@dataclass
class SenatorBundle:
    identity: SenatorIdentity
    terms: list[SenateTerm] = field(default_factory=list)
    exercises: list[SenateExercise] = field(default_factory=list)
    affiliations: list[SenateAffiliation] = field(default_factory=list)
    year_only_claims: list[YearOnlyAffiliationClaim] = field(default_factory=list)
    mandates_document: ArchivedDocument | None = None
    affiliations_document: ArchivedDocument | None = None


@dataclass
class LoadPlan:
    window_starts_on: date
    window_ends_before: date
    senators: list[SenatorBundle]
    parties: list[SenateParty]
    party_catalog_document: ArchivedDocument | None
    pending: list[PendingItem]
    source_summary: dict = field(default_factory=dict)
