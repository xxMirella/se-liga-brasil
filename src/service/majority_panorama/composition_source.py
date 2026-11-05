"""House composition of one legislature, from the annual composition records of a source.

Reference-year rule (fixed, one per house and legislature): the newest year of the legislature,
not after today, whose annual record is reliable. A record is reliable when it documents at
least 90% of the house's seats (81 senators, 513 deputies), has a positive total and names no
more party seats than its total. Without a reliable year the house is `None`: no data.
"""

import math
from datetime import date
from typing import Protocol

from service.majority_panorama.composition_notes import composition_notes
from service.majority_panorama.contracts import HouseComposition, PartyCount
from service.majority_panorama.legislature_windows import reference_year_candidates
from service.majority_panorama.orientation_blocs import (
    classify_political_parties,
    seats_by_political_party,
)

HOUSE_SEATS = {"camara": 513, "senado": 81}
HOUSE_SOURCE_URLS = {
    "camara": "https://www.camara.leg.br/deputados/",
    "senado": "https://www25.senado.leg.br/web/senadores/em-exercicio",
}
MINIMUM_DOCUMENTED_SEAT_SHARE = 0.9


class PanoramaSource(Protocol):
    """What the builder needs; the application adapter implements it over the real database."""

    def annual_composition(self, house, year):
        """Annual record of `house` ("camara" | "senado") in `year`, or None when absent.

        Keys used: total, political_parties [{abbreviation, count, ...}], snapshot_on,
        coverage, institution_code, orientation_policy_version, territory_code, expected_seats.
        """

    def presidency(self):
        """Presidential exercises (see `presidents.collect_presidential_exercises`)."""


def minimum_documented_seats(house):
    return math.ceil(HOUSE_SEATS[house] * MINIMUM_DOCUMENTED_SEAT_SHARE)


def is_reliable_record(house, record):
    if not record:
        return False
    total = record.get("total") or 0
    seats = HOUSE_SEATS[house]
    if not minimum_documented_seats(house) <= total <= seats:
        return False
    return sum(seats_by_political_party(record).values()) <= total


def select_reference_record(house, window, source, today):
    """(reference year, record) for the window, or None when no year is reliable."""
    for year in reference_year_candidates(window, today):
        record = source.annual_composition(house, year)
        if is_reliable_record(house, record):
            return year, record
    return None


def parse_observed_on(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_house_composition(house, window, source, today):
    selected = select_reference_record(house, window, source, today)
    if selected is None:
        return None
    reference_year, record = selected
    counts, parties_by_bloc = classify_political_parties(record, reference_year)
    return HouseComposition(
        house=house,
        total=record["total"],
        seat_counts_by_bloc=counts,
        parties_by_bloc={
            key: tuple(PartyCount(party, seats) for party, seats in entries)
            for key, entries in parties_by_bloc.items()
        },
        reference_year=reference_year,
        observed_on=parse_observed_on(record.get("snapshot_on")),
        source_url=HOUSE_SOURCE_URLS[house],
        notes=composition_notes(
            window, reference_year, record, counts, HOUSE_SEATS[house], today
        ),
    )
