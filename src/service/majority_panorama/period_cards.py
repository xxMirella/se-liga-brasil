"""The three summary cards of a period: Presidência, Senado and Câmara."""

from service.majority_panorama.blocs import BLOC_BY_KEY
from service.majority_panorama.period_selection import (
    largest_ideological_bloc,
    presidents_in_legislature,
    selected_legislature_index,
)
from web_components import BarSegment, render_stacked_bar
from web_components.escaping import escape_text

# Bar order: left to right on the spectrum, with the neutral groups between center and right.
BAR_BLOC_ORDER = (
    "left", "center", "undetermined", "controversial", "unaffiliated", "right", "far_right",
)
CARD_HOUSES = (("senado", "Senado"), ("camara", "Câmara"))


def _card(label, body_html):
    return (
        f'<article class="ds-period-card"><span class="ds-period-card__label">'
        f"{escape_text(label)}</span>{body_html}</article>"
    )


def _render_president(term):
    bloc = BLOC_BY_KEY[term.bloc_key]
    meta = f"{term.political_party_label} · {bloc.label} · {term.span_label}"
    return (
        f'<div class="ds-president"><span class="ds-period-swatch ds-period-swatch--president '
        f'ds-bloc--{term.bloc_key.replace("_", "-")}"></span><div class="ds-president__text">'
        f'<strong class="ds-president__name">{escape_text(term.full_name)}</strong>'
        f'<span class="ds-president__meta">{escape_text(meta)}</span></div></div>'
    )


def render_presidency_card(panorama, legislature):
    terms = presidents_in_legislature(panorama, legislature)
    if not terms:
        return _card(
            "Presidência",
            '<span class="ds-period-card__note">Sem presidente documentado neste período.</span>',
        )
    return _card("Presidência", "".join(_render_president(term) for term in terms))


def _bar_segments(house):
    return [
        BarSegment(key, house.seats(key) / house.total * 100)
        for key in BAR_BLOC_ORDER
    ]


def _bar_description(name, house):
    parts = ", ".join(
        f"{BLOC_BY_KEY[key].label.lower()} {house.seats(key)}"
        for key in BAR_BLOC_ORDER if house.seats(key)
    )
    return f"{name}: {parts} de {house.total}"


def majority_note(house):
    """Whether the largest ideological bloc alone reaches the majority threshold."""
    seats = house.seats(largest_ideological_bloc(house))
    needed = house.majority_threshold
    if seats >= needed:
        return f"Tem maioria sozinho: {seats} de {needed} necessárias."
    return f"Sem maioria sozinho: faltam {needed - seats} para {needed}."


def _render_house_body(name, house):
    top_key = largest_ideological_bloc(house)
    if house.seats(top_key) == 0:
        headline, note = "Nenhum bloco ideológico com cadeiras", ""
    else:
        label = BLOC_BY_KEY[top_key].label
        headline = f"Maior bloco: {label} · {house.seats(top_key)} de {house.total}"
        note = majority_note(house)
    bar = render_stacked_bar(
        _bar_segments(house), _bar_description(name, house), size="sm", half_marker=True
    )
    return (
        f'{bar}<strong class="ds-period-card__headline">{escape_text(headline)}</strong>'
        f'<span class="ds-period-card__note">{escape_text(note)}</span>'
    )


def render_house_card(name, house):
    if house is None:
        body = '<span class="ds-period-card__note">Sem dados: composição não documentada.</span>'
        return _card(name, body)
    return _card(name, _render_house_body(name, house))


def render_period_cards(panorama, state):
    """Grid of the Presidência, Senado and Câmara cards of the selected legislature."""
    legislature = panorama.legislatures[selected_legislature_index(panorama, state)]
    cards = [render_presidency_card(panorama, legislature)] + [
        render_house_card(name, getattr(legislature, key)) for key, name in CARD_HOUSES
    ]
    return f'<div class="ds-period-cards">{"".join(cards)}</div>'
