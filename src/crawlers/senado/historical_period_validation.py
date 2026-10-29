"""Interval rules for the Senate load; pure functions, no network, no database."""

from datetime import date

from crawlers.senado.historical_period_contracts import (
    WINDOW_ENDS_BEFORE,
    WINDOW_STARTS_ON,
)
from service.ingestion.contracts import IngestionError


def overlaps_window(
    starts_on: date,
    ends_before: date | None,
    window_starts_on: date = WINDOW_STARTS_ON,
    window_ends_before: date = WINDOW_ENDS_BEFORE,
) -> bool:
    """Half-open intervals: the end day belongs to the next interval, an open end never closes."""
    return starts_on < window_ends_before and (
        ends_before is None or ends_before > window_starts_on
    )


def ensure_valid_interval(starts_on: date, ends_before: date | None, label: str) -> None:
    if ends_before is not None and ends_before <= starts_on:
        raise IngestionError("INVALID_INTERVAL", {"interval": label})


def ensure_disjoint(intervals: list[tuple[date, date | None, str]]) -> None:
    """Refuse any overlap, including an open interval followed by another one."""
    ordered = sorted(intervals, key=lambda row: (row[0], row[1] or date.max))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous[1] is None or previous[1] > current[0]:
            raise IngestionError(
                "OVERLAPPING_INTERVALS", {"first": previous[2], "second": current[2]}
            )


def ensure_exercise_within_term(exercise_starts_on, exercise_ends_before, term) -> None:
    ends_inside = exercise_ends_before is None or exercise_ends_before <= term.ends_before
    if exercise_starts_on < term.starts_on or not ends_inside:
        raise IngestionError(
            "EXERCISE_OUTSIDE_TERM",
            {"exercise_starts_on": str(exercise_starts_on), "term": term.legislature_key},
        )
