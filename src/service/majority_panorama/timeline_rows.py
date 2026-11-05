"""Timeline "Por período": one link per legislature, newest first, with presidents and bars."""

from service.majority_panorama.bloc_view import (
    HOUSE_NAMES,
    bloc_label,
    house_bar_label,
    house_bar_segments,
    houses_of,
    legend_entries,
)
from service.majority_panorama.selection import presidents_in_legislature, selected_legislature
from web_components import render_bloc_legend, render_bloc_swatch, render_stacked_bar
from web_components.escaping import escape_text

PERIOD_HINT = (
    "Toque num período para ver as cadeiras e montar coalizões. "
    "Esquerda sempre à esquerda da barra, direita à direita."
)


def data_tag(legislature):
    if legislature.has_data:
        return "dados do Se Liga"
    if legislature.camara is None and legislature.senado is None:
        return "sem dados"
    return "dados parciais"


def _render_president(term):
    return (
        '<span class="ds-timeline-row__president">'
        f"{render_bloc_swatch(term.bloc_key, size='sm')}"
        f"<span><strong>{escape_text(term.short_name)}</strong> "
        f"{escape_text(term.political_party_label)} · {escape_text(bloc_label(term.bloc_key))}"
        "</span></span>"
    )


def _render_house_line(house_key, legislature, house):
    bar = render_stacked_bar(
        house_bar_segments(house),
        house_bar_label(HOUSE_NAMES[house_key], legislature.label, house),
        size="md",
        half_marker=True,
    )
    return (
        '<div class="ds-timeline-row__house">'
        f'<span class="ds-timeline-row__house-name">{HOUSE_NAMES[house_key]}</span>{bar}</div>'
    )


def _render_houses(legislature):
    houses = houses_of(legislature)
    if not houses:
        return '<p class="ds-timeline-row__no-data">sem dados</p>'
    return "".join(_render_house_line(key, legislature, house) for key, house in houses)


def _render_row(panorama, state, legislature, selected_id):
    current = ' aria-current="true"' if legislature.legislature_id == selected_id else ""
    url = state.link("periodo", legislature_id=legislature.legislature_id, highlight=None)
    presidents = "".join(
        _render_president(term) for term in presidents_in_legislature(panorama, legislature)
    )
    return (
        f'<li><a class="ds-timeline-row" href="{escape_text(url)}"{current}>'
        f'<div class="ds-timeline-row__period"><strong>{escape_text(legislature.label)}</strong>'
        f'<span class="ds-timeline-row__tag">{data_tag(legislature)}</span></div>'
        f'<div class="ds-timeline-row__presidents">{presidents}</div>'
        f'<div class="ds-timeline-row__houses">{_render_houses(legislature)}</div></a></li>'
    )


def render_period_timeline(panorama, state):
    """Legend, dashed-line key and the list of legislatures, most recent first."""
    selected = selected_legislature(panorama, state)
    selected_id = selected.legislature_id if selected else None
    rows = "".join(
        _render_row(panorama, state, legislature, selected_id)
        for legislature in reversed(panorama.legislatures)
    )
    legend = render_bloc_legend(
        legend_entries(panorama), compact=True, half_marker_label="metade das cadeiras"
    )
    return (
        '<div class="ds-timeline__period-view">'
        f'{legend}<ol class="ds-timeline__rows">{rows}</ol>'
        f'<p class="ds-timeline__hint">{escape_text(PERIOD_HINT)}</p></div>'
    )
