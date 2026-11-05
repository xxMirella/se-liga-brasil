"""Seat groups and legend entries of one house, colored by bloc or by political party."""

from dataclasses import dataclass

from service.majority_panorama.blocs import BLOC_BY_KEY, BLOC_KEYS, bloc_color
from web_components.parliament_chart import SeatGroup

CHROMA_BY_BLOC = {"center": 0.12}
DEFAULT_CHROMA = 0.14
LIGHTNESS_FIRST = 0.36
LIGHTNESS_RANGE = 0.42
LONE_PARTY_LIGHTNESS = 0.5


@dataclass(frozen=True)
class LegendParty:
    political_party: str
    seat_count: int
    fill: str


@dataclass(frozen=True)
class LegendBloc:
    bloc_key: str
    seat_count: int
    fill: str
    political_parties: tuple[LegendParty, ...]


def political_party_shade(bloc_key, index, count):
    """Tone of one party inside its bloc: same hue, darker to lighter by seat-count order."""
    bloc = BLOC_BY_KEY[bloc_key]
    if bloc.hue is None:
        return bloc_color(bloc_key)
    lightness = (
        LONE_PARTY_LIGHTNESS if count <= 1
        else LIGHTNESS_FIRST + LIGHTNESS_RANGE * index / (count - 1)
    )
    chroma = CHROMA_BY_BLOC.get(bloc_key, DEFAULT_CHROMA)
    return f"oklch({lightness:.3f} {chroma} {bloc.hue})"


def has_party_detail(house):
    """True when every bloc with seats lists parties whose seats add up to the bloc's seats."""
    if house is None:
        return False
    for bloc_key in BLOC_KEYS:
        seats = house.seats(bloc_key)
        parties = house.parties_by_bloc.get(bloc_key, ())
        if seats and sum(party.seat_count for party in parties) not in (0, seats):
            return False
    return any(house.parties_by_bloc.values())


def effective_color_mode(house, requested_mode):
    """Party colors are only possible with party detail; otherwise colors follow the bloc."""
    return requested_mode if requested_mode == "partido" and has_party_detail(house) else "bloco"


def _legend_parties(house, bloc_key, mode):
    if mode != "partido":
        return ()
    parties = house.parties_by_bloc.get(bloc_key, ())
    return tuple(
        LegendParty(
            party.political_party, party.seat_count,
            political_party_shade(bloc_key, index, len(parties)),
        )
        for index, party in enumerate(parties)
    )


def build_legend(house, mode):
    """One entry per bloc that holds seats, in `BLOC_KEYS` order (left to right)."""
    return tuple(
        LegendBloc(key, house.seats(key), bloc_color(key), _legend_parties(house, key, mode))
        for key in BLOC_KEYS if house.seats(key)
    )


def build_seat_groups(legend):
    """Seat groups in drawing order: by party when the legend lists parties, else by bloc."""
    groups = []
    for bloc in legend:
        if bloc.political_parties:
            groups.extend(
                SeatGroup(party.political_party, bloc.bloc_key, party.seat_count, party.fill)
                for party in bloc.political_parties
            )
        else:
            groups.append(SeatGroup(bloc.bloc_key, bloc.bloc_key, bloc.seat_count, bloc.fill))
    return tuple(groups)
