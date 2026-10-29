"""Calendar slices used to group roll calls. Pure functions and constants."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Legislature:
    number: int
    first_year: int
    last_year: int

    @property
    def label(self) -> str:
        return f"{self.number}a legislatura ({self.first_year}-{self.last_year})"


# Terms begin on 1 February; roll calls of January (recess) are assigned to the calendar slice.
LEGISLATURES = tuple(
    Legislature(number, first, first + 3) for number, first in enumerate(range(1991, 2027, 4), 49)
)

# Presidential periods, from the official Presidency chronology; used only to read the
# alignment with the government of the day, never to infer ideology.
GOVERNMENTS = (
    ("FHC II", date(1999, 1, 1), date(2002, 12, 31)),
    ("Lula I", date(2003, 1, 1), date(2006, 12, 31)),
    ("Lula II", date(2007, 1, 1), date(2010, 12, 31)),
    ("Dilma I", date(2011, 1, 1), date(2014, 12, 31)),
    ("Dilma II", date(2015, 1, 1), date(2016, 5, 11)),
    ("Temer", date(2016, 5, 12), date(2018, 12, 31)),
    ("Bolsonaro", date(2019, 1, 1), date(2022, 12, 31)),
    ("Lula III", date(2023, 1, 1), date(2026, 12, 31)),
)


def legislature_of(year: int) -> Legislature:
    for legislature in LEGISLATURES:
        if legislature.first_year <= year <= legislature.last_year:
            return legislature
    raise ValueError(f"year outside modelled legislatures: {year}")


def government_on(day: date) -> str | None:
    for name, start, end in GOVERNMENTS:
        if start <= day <= end:
            return name
    return None
