"""The "Período selecionado" section: legislature heading, verdict, summary cards and seats."""

from service.majority_panorama.period_cards import render_period_cards
from service.majority_panorama.period_selection import selected_legislature_index
from service.majority_panorama.period_verdict import build_period_verdict
from service.majority_panorama.seats_card import render_seats_card
from web_components.escaping import escape_text

FRAGMENT = "periodo"


def _step_link(text, aria_label, panorama, state, target_index):
    if not 0 <= target_index < len(panorama.legislatures):
        return (
            f'<span class="ds-period__step ds-period__step--disabled" aria-disabled="true" '
            f'aria-label="{escape_text(aria_label)}">{escape_text(text)}</span>'
        )
    target = panorama.legislatures[target_index]
    url = state.link(FRAGMENT, legislature_id=target.legislature_id, highlight=None)
    return (
        f'<a class="ds-period__step" href="{escape_text(url)}" '
        f'aria-label="{escape_text(aria_label)}">{escape_text(text)}</a>'
    )


def _render_heading(panorama, state, index):
    label = panorama.legislatures[index].label
    return (
        '<div class="ds-period__heading"><div class="ds-period__title">'
        '<span class="ds-period__eyebrow">Período selecionado</span>'
        f'<h2 class="ds-period__label">{escape_text(label)}</h2></div>'
        '<nav class="ds-period__steps" aria-label="Trocar de período">'
        f'{_step_link("‹ Anterior", "Período anterior", panorama, state, index - 1)}'
        f'{_step_link("Próximo ›", "Próximo período", panorama, state, index + 1)}</nav></div>'
    )


def render_period_section(panorama, state):
    """Full `<section id="periodo">` for the legislature chosen by `state`."""
    if not panorama.legislatures:
        return (
            f'<section class="ds-period" id="{FRAGMENT}"><p class="ds-period__verdict">'
            "Sem dados: nenhuma legislatura documentada.</p></section>"
        )
    index = selected_legislature_index(panorama, state)
    verdict = build_period_verdict(panorama, panorama.legislatures[index])
    return (
        f'<section class="ds-period" id="{FRAGMENT}">{_render_heading(panorama, state, index)}'
        f'<p class="ds-period__verdict">{escape_text(verdict)}</p>'
        f"{render_period_cards(panorama, state)}{render_seats_card(panorama, state)}</section>"
    )
