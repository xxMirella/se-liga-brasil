"""HTML of the "Entenda a regra" card (the chocolate example); see explainer.py for the logic."""

from service.majority_panorama.explainer import (
    POPULATION_GROUPS,
    PROPOSAL_LABELS,
    SCENARIO_LABELS,
    TOTAL_PEOPLE,
    build_chocolate_explanation,
)
from web_components import (
    BarSegment,
    ChoiceLink,
    render_bloc_swatch,
    render_choice_links,
    render_dot_grid,
    render_stacked_bar,
)
from web_components.escaping import escape_text

CARD_FRAGMENT = "entenda-a-regra"


def _population_bar():
    segments = [
        BarSegment(group.color_key, group.population_percent) for group in POPULATION_GROUPS
    ]
    label = "Na população: " + ", ".join(
        f"{group.label} {group.population_percent}%" for group in POPULATION_GROUPS
    )
    return render_stacked_bar(segments, label, size="lg")


def _groups_legend():
    items = "".join(
        '<span class="ds-rule-card__group">'
        f"{render_bloc_swatch(group.color_key, size='sm', round_shape=True)}"
        f"<span>{escape_text(group.label)} "
        f"<strong>{group.population_percent}</strong></span></span>"
        for group in POPULATION_GROUPS
    )
    return f'<div class="ds-rule-card__groups">{items}</div>'


def _scenario_choices(state):
    return [
        ChoiceLink(label, state.link(CARD_FRAGMENT, scenario=key), state.scenario == key)
        for key, label in SCENARIO_LABELS.items()
    ]


def _proposal_choices(state):
    return [
        ChoiceLink(label, state.link(CARD_FRAGMENT, proposal=key), state.proposal == key)
        for key, label in PROPOSAL_LABELS.items()
    ]


def _population_block():
    return (
        '<div class="ds-rule-card__block">'
        f'<span class="ds-rule-card__heading">Na população: {TOTAL_PEOPLE} pessoas</span>'
        f"{_population_bar()}{_groups_legend()}</div>"
    )


def _seats_block(explanation, state):
    return (
        '<div class="ds-rule-card__block">'
        '<span class="ds-rule-card__heading">Nas 100 cadeiras de quem vota por elas</span>'
        f"{render_choice_links('Composição das cadeiras', _scenario_choices(state))}"
        f"{render_dot_grid(explanation.seat_group_keys)}"
        f'<span class="ds-rule-card__seats-text">{escape_text(explanation.seats_text)}</span>'
        "</div>"
    )


def _vote_block(explanation, state):
    outcome = "approved" if explanation.approved else "rejected"
    unrepresented = ""
    if explanation.unrepresented_text:
        unrepresented = (
            '<div class="ds-rule-card__unrepresented"><strong>Sem representação.</strong> '
            f"{escape_text(explanation.unrepresented_text)}</div>"
        )
    return (
        '<div class="ds-rule-card__block">'
        '<span class="ds-rule-card__heading">Proposta em votação</span>'
        f"{render_choice_links('Proposta', _proposal_choices(state), variant='option')}"
        f'<div class="ds-rule-card__vote ds-rule-card__vote--{outcome}" role="status">'
        f"<strong>{escape_text(explanation.vote_title)}</strong> "
        f"{escape_text(explanation.vote_text)}</div>{unrepresented}</div>"
    )


def render_rule_explainer(state):
    """Card "Entenda a regra · quem está representado?"; `state` supplies scenario and proposal."""
    explanation = build_chocolate_explanation(state.scenario, state.proposal)
    return (
        f'<div class="ds-rule-card" id="{CARD_FRAGMENT}">'
        '<span class="ds-rule-card__eyebrow">Entenda a regra · quem está representado?</span>'
        f"{_population_block()}{_seats_block(explanation, state)}"
        f"{_vote_block(explanation, state)}</div>"
    )
