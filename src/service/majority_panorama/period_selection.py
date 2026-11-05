"""Which legislature the reader is looking at, who presided it and which bloc is largest."""

from datetime import date

from service.majority_panorama.blocs import IDEOLOGICAL_BLOC_KEYS


def selected_legislature_index(panorama, state):
    """Index of the chosen legislature; no (or an unknown) id selects the most recent one."""
    for index, legislature in enumerate(panorama.legislatures):
        if legislature.legislature_id == state.legislature_id:
            return index
    return len(panorama.legislatures) - 1


def _overlap_days(term, legislature):
    start = max(term.start_on, date(legislature.first_year, 1, 1))
    end = min(term.end_on, date(legislature.end_year_exclusive, 1, 1))
    return (end - start).days


def presidents_in_legislature(panorama, legislature):
    return tuple(
        term for term in panorama.presidents if _overlap_days(term, legislature) > 0
    )


def main_president(panorama, legislature):
    """President with the longest overlap with the legislature; the earliest wins a tie."""
    terms = presidents_in_legislature(panorama, legislature)
    if not terms:
        return None
    return max(terms, key=lambda term: _overlap_days(term, legislature))


def largest_ideological_bloc(house):
    """Bloc key with the most seats among the ideological blocs; the leftmost wins a tie."""
    return max(IDEOLOGICAL_BLOC_KEYS, key=house.seats)


def has_solo_majority(house):
    return house.seats(largest_ideological_bloc(house)) >= house.majority_threshold


def format_percent(part, whole):
    return f"{part / whole * 100:.1f}".replace(".", ",") + "%"
