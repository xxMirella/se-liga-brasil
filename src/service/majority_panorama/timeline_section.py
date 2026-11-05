"""Timeline section of the panorama: who governed and who held the seats, by period or by bloc."""

from service.majority_panorama.bloc_view import bloc_label, present_bloc_keys
from service.majority_panorama.selection import series_first_year
from service.majority_panorama.timeline_blocs import render_bloc_timeline
from service.majority_panorama.timeline_rows import render_period_timeline
from web_components import ChoiceLink, render_choice_links
from web_components.escaping import escape_text

SECTION_ID = "linha-do-tempo"
VIEW_LABELS = (("periodo", "Por período"), ("bloco", "Por bloco"))
LEAD = (
    "Veja período a período quem governou e como cada Casa se dividiu, ou escolha um bloco "
    "para acompanhar a força dele ao longo do tempo."
)
CALLOUT_TITLE = "Quase nunca um bloco tem maioria sozinho."
CALLOUT_TEXT = (
    " Por isso presidentes formam coalizões: somam partidos de mais de um bloco para chegar "
    "à metade das cadeiras e aprovar leis."
)


def series_title(panorama):
    year = series_first_year(panorama)
    since = f", de {year} a hoje" if year is not None else ""
    return f"Quem governou e quem teve maioria{since}"


def _view_choices(state):
    return [
        ChoiceLink(label, state.link(SECTION_ID, timeline_view=key), state.timeline_view == key)
        for key, label in VIEW_LABELS
    ]


def _bloc_choices(panorama, state):
    return [
        ChoiceLink(
            bloc_label(key), state.link(SECTION_ID, timeline_bloc=key),
            state.timeline_bloc == key, bloc_key=key,
        )
        for key in present_bloc_keys(panorama)
    ]


def _controls(panorama, state):
    picker = ""
    if state.timeline_view == "bloco":
        picker = render_choice_links("Bloco", _bloc_choices(panorama, state), variant="swatch")
    views = render_choice_links("Como ver", _view_choices(state), variant="segmented")
    return f'<div class="ds-timeline__controls">{views}{picker}</div>'


def _callout():
    return (
        '<div class="ds-timeline__callout"><span class="ds-timeline__callout-mark" '
        'aria-hidden="true">!</span>'
        f"<p><strong>{escape_text(CALLOUT_TITLE)}</strong>{escape_text(CALLOUT_TEXT)}</p></div>"
    )


def render_timeline_section(panorama, state):
    """`<section id="linha-do-tempo">`: title, view switch, period list or bloc charts, callout."""
    body = (
        render_bloc_timeline(panorama, state)
        if state.timeline_view == "bloco"
        else render_period_timeline(panorama, state)
    )
    return (
        f'<section class="ds-timeline" id="{SECTION_ID}" data-screen-label="Linha do tempo">'
        '<div class="ds-timeline__header">'
        f'<h2 class="ds-timeline__title">{escape_text(series_title(panorama))}</h2>'
        f'<p class="ds-timeline__lead">{escape_text(LEAD)}</p></div>'
        f"{_controls(panorama, state)}{body}{_callout()}</section>"
    )
