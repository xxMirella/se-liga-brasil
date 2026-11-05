"""Data contract between the panorama data builder and its renderers. Pure data, no I/O."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class PartyCount:
    political_party: str
    seat_count: int


@dataclass(frozen=True)
class HouseComposition:
    """One house of Congress in one legislature, counted per bloc and, when known, per party."""

    house: str  # "camara" | "senado"
    total: int
    seat_counts_by_bloc: Mapping[str, int]  # keys from blocs.BLOC_KEYS; absent key means zero
    parties_by_bloc: Mapping[str, tuple[PartyCount, ...]]  # parties ordered by seat_count desc
    reference_year: int
    observed_on: date | None = None  # exact observation date when the source gives one
    source_url: str | None = None
    notes: tuple[str, ...] = ()  # coverage caveats shown to the reader, never hidden

    def seats(self, bloc_key):
        return self.seat_counts_by_bloc.get(bloc_key, 0)

    @property
    def majority_threshold(self):
        return self.total // 2 + 1


@dataclass(frozen=True)
class Legislature:
    legislature_id: str  # first year of the term, e.g. "2023"
    first_year: int
    end_year_exclusive: int
    label: str  # "2023–2026"
    camara: HouseComposition | None  # None: no documented composition for this period
    senado: HouseComposition | None

    @property
    def has_data(self):
        return self.camara is not None and self.senado is not None


@dataclass(frozen=True)
class PresidentialTerm:
    full_name: str
    short_name: str
    political_party_label: str  # as documented, e.g. "PSL / PL" or "sem partido"
    bloc_key: str
    start_on: date
    end_on: date  # exclusive end; the incumbent term ends at the next presidential transition
    span_label: str  # "2023–2026"
    source_url: str | None = None
    notes: tuple[str, ...] = ()  # party-label and bloc-classification caveats
    bloc_evidence_urls: tuple[str, ...] = ()  # reviewed sources behind the bloc


@dataclass(frozen=True)
class MajorityPanorama:
    legislatures: tuple[Legislature, ...]  # chronological order
    presidents: tuple[PresidentialTerm, ...]  # chronological order
    generated_on: date
    sources_note: str = ""  # where the numbers come from, with observation dates
    coverage_notes: tuple[str, ...] = field(default=())
