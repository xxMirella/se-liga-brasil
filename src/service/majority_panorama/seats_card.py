"""The seats card: house tabs, color mode, hemicycle chart and the clickable legend."""

from service.majority_panorama.blocs import BLOC_BY_KEY
from service.majority_panorama.period_selection import (
    format_percent,
    selected_legislature_index,
)
from service.majority_panorama.seat_groups import (
    build_legend,
    build_seat_groups,
    effective_color_mode,
    has_party_detail,
)
from web_components.escaping import escape_text
from web_components.parliament_chart import render_parliament_chart

FRAGMENT = "cadeiras"
HOUSE_LABELS = (("camara", "Câmara"), ("senado", "Senado"))
HOUSE_FULL_NAMES = {"camara": "Câmara dos Deputados", "senado": "Senado Federal"}
COLOR_MODE_LABELS = (("partido", "Cor por partido"), ("bloco", "Cor por bloco"))


def _tab_label(label, house):
    return f"{label} · {house.total}" if house is not None else f"{label} · sem dados"


def _house_url(state, house_key):
    return escape_text(state.link(FRAGMENT, house=house_key, highlight=None))


def _render_house_tabs(legislature, state):
    items = "".join(
        f'<a class="ds-seats-tabs__tab" href="{_house_url(state, key)}"'
        + (' aria-current="page"' if state.house == key else "")
        + f">{escape_text(_tab_label(label, getattr(legislature, key)))}</a>"
        for key, label in HOUSE_LABELS
    )
    return f'<nav class="ds-seats-tabs" aria-label="Casa">{items}</nav>'


def _render_mode_option(key, label, state, current, enabled):
    if not enabled:
        return (
            f'<span class="ds-seats-modes__option ds-seats-modes__option--disabled" '
            f'aria-disabled="true">{escape_text(label)}</span>'
        )
    current_attribute = ' aria-current="true"' if key == current else ""
    url = escape_text(state.link(FRAGMENT, color_mode=key))
    return (
        f'<a class="ds-seats-modes__option" href="{url}"{current_attribute}>'
        f"{escape_text(label)}</a>"
    )


def _render_color_modes(house, state, mode):
    detail = has_party_detail(house)
    options = "".join(
        _render_mode_option(key, label, state, mode, enabled=detail or key == "bloco")
        for key, label in COLOR_MODE_LABELS
    )
    return f'<div class="ds-seats-modes" role="group" aria-label="Cores">{options}</div>'


def _toggle_url(state, key):
    return escape_text(state.link(FRAGMENT, highlight=None if state.highlight == key else key))


def _pressed(state, key):
    return ' aria-current="true"' if state.highlight == key else ""


def _render_legend_party(party, state):
    return (
        f'<a class="ds-seat-legend__party" href="{_toggle_url(state, party.political_party)}"'
        f'{_pressed(state, party.political_party)}>'
        f'<svg class="ds-seat-legend__dot" viewBox="0 0 10 10" aria-hidden="true" '
        f'focusable="false"><circle cx="5" cy="5" r="5" fill="{escape_text(party.fill)}"/></svg>'
        f"{escape_text(party.political_party)} <strong>{party.seat_count}</strong></a>"
    )


def _render_legend_bloc(bloc, total, state):
    bloc_class = "ds-bloc--" + bloc.bloc_key.replace("_", "-")
    parties = "".join(_render_legend_party(party, state) for party in bloc.political_parties)
    parties_html = f'<div class="ds-seat-legend__parties">{parties}</div>' if parties else ""
    return (
        f'<div class="ds-seat-legend__group"><a class="ds-seat-legend__bloc" '
        f'href="{_toggle_url(state, bloc.bloc_key)}"{_pressed(state, bloc.bloc_key)}>'
        '<span class="ds-seat-legend__name">'
        f'<span class="ds-period-swatch ds-period-swatch--legend '
        f'{bloc_class}"></span>{escape_text(BLOC_BY_KEY[bloc.bloc_key].label)}</span>'
        f'<span class="ds-seat-legend__count"><strong>{bloc.seat_count}</strong> · '
        f"{format_percent(bloc.seat_count, total)}</span></a>{parties_html}</div>"
    )


def _chart_description(house_name, house, legend):
    counts = ", ".join(
        f"{BLOC_BY_KEY[bloc.bloc_key].label.lower()} {bloc.seat_count}" for bloc in legend
    )
    return f"{house_name}: {house.total} cadeiras ({counts}). Maioria: {house.majority_threshold}."


def _known_highlight(highlight, groups):
    """Ignore a highlight that names nothing in this chamber (a stale or mistyped link)."""
    known = {key for group in groups for key in (group.group_key, group.bloc_key)}
    return highlight if highlight in known else None


def _render_house_body(legislature, state):
    house = getattr(legislature, state.house)
    house_name = HOUSE_FULL_NAMES[state.house]
    if house is None:
        return (
            f'<p class="ds-seats-card__footnote">Sem dados: o Se Liga não tem a composição do '
            f"{escape_text(house_name)} para {escape_text(legislature.label)}.</p>"
        )
    mode = effective_color_mode(house, state.color_mode)
    legend = build_legend(house, mode)
    groups = build_seat_groups(legend)
    chart = render_parliament_chart(
        groups, house.total, house.majority_threshold,
        _chart_description(house_name, house, legend),
        highlight=_known_highlight(state.highlight, groups),
    )
    legend_html = "".join(_render_legend_bloc(bloc, house.total, state) for bloc in legend)
    return (
        f'<div class="ds-seats-card__body"><div class="ds-seats-card__chart">{chart}'
        f"</div>"
        f'<div class="ds-seat-legend">{legend_html}</div></div>'
    )


def render_seats_card(panorama, state):
    """Seats card of the selected legislature and house, as HTML."""
    legislature = panorama.legislatures[selected_legislature_index(panorama, state)]
    house = getattr(legislature, state.house)
    mode = effective_color_mode(house, state.color_mode)
    return (
        f'<div class="ds-seats-card" id="{FRAGMENT}"><div class="ds-seats-card__controls">'
        f"{_render_house_tabs(legislature, state)}{_render_color_modes(house, state, mode)}"
        f"</div>{_render_house_body(legislature, state)}</div>"
    )
