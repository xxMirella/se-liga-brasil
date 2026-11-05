"""Presentation helpers shared by the panorama sections: bloc order, labels, bar segments."""

from service.majority_panorama.blocs import BLOC_BY_KEY, BLOCS
from web_components import BarSegment

# Left to right on every bar. Groups without a position sit in the middle, like the prototype's
# "sem partido" segment; the far right closes the right edge.
BAR_ORDER = (
    "left", "center", "undetermined", "controversial", "unaffiliated", "right", "far_right",
)
HOUSE_NAMES = {"senado": "Senado", "camara": "Câmara"}


def bloc_label(bloc_key):
    return BLOC_BY_KEY[bloc_key].label


def rounded_percent(count, total):
    """Whole-number percent, half rounded up (never banker's rounding)."""
    return int(count * 100 / total + 0.5) if total else 0


def decimal_percent_text(count, total):
    """`37,5%` with a decimal comma."""
    return f"{count / total * 100:.1f}".replace(".", ",") + "%" if total else "0,0%"


def house_bar_segments(house):
    segments = []
    for bloc_key in BAR_ORDER:
        seats = house.seats(bloc_key)
        if seats > 0:
            percent = seats / house.total * 100
            text = f"{rounded_percent(seats, house.total)}%"
            segments.append(BarSegment(bloc_key, percent, text))
    return segments


def house_bar_label(house_name, legislature_label, house):
    parts = ", ".join(
        f"{bloc_label(key)} {house.seats(key)}" for key in BAR_ORDER if house.seats(key) > 0
    )
    return f"{house_name} {legislature_label}: {parts} de {house.total}"


def houses_of(legislature):
    """(key, composition) for the houses that have data, Senado first like the prototype."""
    return [
        (key, house)
        for key, house in (("senado", legislature.senado), ("camara", legislature.camara))
        if house is not None
    ]


def present_bloc_keys(panorama):
    """Ideological blocs, plus the neutral groups that hold seats in at least one house."""
    present = {
        key
        for legislature in panorama.legislatures
        for _, house in houses_of(legislature)
        for key, seats in house.seat_counts_by_bloc.items()
        if seats > 0
    }
    return tuple(bloc.key for bloc in BLOCS if bloc.ideological or bloc.key in present)


def legend_entries(panorama):
    return [(key, bloc_label(key)) for key in present_bloc_keys(panorama)]

