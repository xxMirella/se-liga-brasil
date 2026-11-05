"""Political blocs shown by the panorama: the project's orientation categories, left to right.

The three reference blocs (left, center, right) plus the catalog's "far right" and three neutral
groups. Nothing here classifies a party; classification comes from the orientation catalog.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bloc:
    key: str
    label: str
    hue: int | None  # oklch hue of the bloc; None for neutral groups
    ideological: bool  # only ideological blocs compete for "largest bloc" and majority arithmetic


BLOCS = (
    Bloc("left", "Esquerda", 25, True),
    Bloc("center", "Centro", 75, True),
    Bloc("right", "Direita", 250, True),
    Bloc("far_right", "Extrema direita", 295, True),
    Bloc("undetermined", "Sem classificação", None, False),
    Bloc("controversial", "Classificação controversa", None, False),
    Bloc("unaffiliated", "Sem filiação", None, False),
)
BLOC_BY_KEY = {bloc.key: bloc for bloc in BLOCS}
IDEOLOGICAL_BLOC_KEYS = tuple(bloc.key for bloc in BLOCS if bloc.ideological)
NEUTRAL_BLOC_KEYS = tuple(bloc.key for bloc in BLOCS if not bloc.ideological)
BLOC_KEYS = tuple(bloc.key for bloc in BLOCS)
NEUTRAL_COLORS = {
    "undetermined": "#bdb8ad",
    "controversial": "#a89fb0",
    "unaffiliated": "#d6d1c6",
}


def bloc_color(key):
    bloc = BLOC_BY_KEY[key]
    if bloc.hue is None:
        return NEUTRAL_COLORS[key]
    return f"oklch(0.5 0.14 {bloc.hue})"
