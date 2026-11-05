"""Panorama view state. Every interaction is a link: the state lives in the query string."""

from dataclasses import dataclass, replace
from urllib.parse import urlencode

from service.majority_panorama.blocs import BLOC_KEYS

PANORAMA_PATH = "/panorama"
HOUSES = ("camara", "senado")
COLOR_MODES = ("partido", "bloco")
SCENARIOS = ("prop", "conc", "equi")
PROPOSALS = ("A", "B")
TIMELINE_VIEWS = ("periodo", "bloco")
QUERY_PARAMETERS = frozenset({"leg", "house", "mode", "hl", "scen", "prop", "view", "bloc"})
MAX_HIGHLIGHT_LENGTH = 40


@dataclass(frozen=True)
class PanoramaState:
    legislature_id: str | None = None  # None: the most recent legislature
    house: str = "camara"
    color_mode: str = "partido"
    highlight: str | None = None  # a bloc key or a political party abbreviation
    scenario: str = "prop"
    proposal: str = "B"
    timeline_view: str = "periodo"
    timeline_bloc: str = "right"

    def with_changes(self, **changes):
        return replace(self, **changes)

    def link(self, fragment, **changes):
        """URL for the state after `changes`, ending at `#fragment`; default values are omitted."""
        state = replace(self, **changes)
        default = PanoramaState()
        pairs = (
            ("leg", state.legislature_id, None), ("house", state.house, default.house),
            ("mode", state.color_mode, default.color_mode), ("hl", state.highlight, None),
            ("scen", state.scenario, default.scenario), ("prop", state.proposal, default.proposal),
            ("view", state.timeline_view, default.timeline_view),
            ("bloc", state.timeline_bloc, default.timeline_bloc),
        )
        query = urlencode([(name, value) for name, value, fallback in pairs if value != fallback])
        return PANORAMA_PATH + (f"?{query}" if query else "") + f"#{fragment}"


def _choice(value, allowed, name):
    if value not in allowed:
        raise ValueError(f"INVALID_PANORAMA_PARAMETER:{name}")
    return value


def parse_state(parameters):
    """Validate query parameters (already limited to QUERY_PARAMETERS) into a PanoramaState."""
    default = PanoramaState()
    highlight = parameters.get("hl")
    if highlight is not None and len(highlight) > MAX_HIGHLIGHT_LENGTH:
        raise ValueError("INVALID_PANORAMA_PARAMETER:hl")
    legislature_id = parameters.get("leg")
    if legislature_id is not None and not (legislature_id.isascii() and legislature_id.isdigit()):
        raise ValueError("INVALID_PANORAMA_PARAMETER:leg")
    return PanoramaState(
        legislature_id=legislature_id,
        house=_choice(parameters.get("house", default.house), HOUSES, "house"),
        color_mode=_choice(parameters.get("mode", default.color_mode), COLOR_MODES, "mode"),
        highlight=highlight,
        scenario=_choice(parameters.get("scen", default.scenario), SCENARIOS, "scen"),
        proposal=_choice(parameters.get("prop", default.proposal), PROPOSALS, "prop"),
        timeline_view=_choice(
            parameters.get("view", default.timeline_view), TIMELINE_VIEWS, "view"
        ),
        timeline_bloc=_choice(parameters.get("bloc", default.timeline_bloc), BLOC_KEYS, "bloc"),
    )
