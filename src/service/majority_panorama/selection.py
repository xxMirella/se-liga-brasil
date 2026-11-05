"""Which legislature is selected, and which presidents governed during it. Pure functions."""

from datetime import date


def selected_legislature(panorama, state):
    """The legislature named by the state, else the most recent one (None when there is none)."""
    by_id = {legislature.legislature_id: legislature for legislature in panorama.legislatures}
    if state.legislature_id in by_id:
        return by_id[state.legislature_id]
    return panorama.legislatures[-1] if panorama.legislatures else None


def presidents_in_legislature(panorama, legislature):
    """Presidential terms that overlap the legislature, in chronological order."""
    starts_on = date(legislature.first_year, 1, 1)
    ends_on = date(legislature.end_year_exclusive, 1, 1)
    return tuple(
        term for term in panorama.presidents if term.start_on < ends_on and term.end_on > starts_on
    )


def series_first_year(panorama):
    """First year of the presidential series (1985 in the current data)."""
    if panorama.presidents:
        return min(term.start_on.year for term in panorama.presidents)
    return panorama.legislatures[0].first_year if panorama.legislatures else None
