"""Four-year legislature windows (1983 onward) and the years a legislature may be sampled at."""

from dataclasses import dataclass
from datetime import date

FIRST_LEGISLATURE_YEAR = 1983
LEGISLATURE_LENGTH_YEARS = 4


@dataclass(frozen=True)
class LegislatureWindow:
    first_year: int

    @property
    def end_year_exclusive(self):
        return self.first_year + LEGISLATURE_LENGTH_YEARS

    @property
    def last_year(self):
        return self.end_year_exclusive - 1

    @property
    def legislature_id(self):
        return str(self.first_year)

    @property
    def label(self):
        return f"{self.first_year}–{self.last_year}"

    @property
    def ends_on_exclusive(self):
        return date(self.end_year_exclusive, 1, 1)


def legislature_windows(today):
    """Every window from 1983–1986 up to the one that contains `today`, chronologically."""
    first_years = range(FIRST_LEGISLATURE_YEAR, today.year + 1, LEGISLATURE_LENGTH_YEARS)
    return tuple(LegislatureWindow(first_year) for first_year in first_years)


def window_containing(day, today):
    """The window that contains `day`; None before 1983."""
    for window in legislature_windows(today):
        if window.first_year <= day.year < window.end_year_exclusive:
            return window
    return None


def reference_year_candidates(window, today):
    """Years of the window in the order they are tried: newest first, never after today."""
    newest = min(window.last_year, today.year)
    return range(newest, window.first_year - 1, -1)
