"""Opening section of the panorama: headline, bloc legend and the "who is represented?" card."""

from service.majority_panorama.bloc_view import legend_entries
from service.majority_panorama.explainer_view import render_rule_explainer
from service.majority_panorama.selection import series_first_year
from web_components import render_bloc_legend, render_eyebrow
from web_components.escaping import escape_text

LEAD_BASE = (
    "Leis são aprovadas por votação. Quem soma mais da metade das cadeiras decide o resultado. "
    "Veja como Presidência, Senado e Câmara se dividiram"
)


def _lead(panorama):
    year = series_first_year(panorama)
    since = f" desde {year}" if year is not None else ""
    return f"{LEAD_BASE}{since}."


def render_opening_section(panorama, state):
    """`<section data-screen-label="Abertura">`: intro beside the explainer card."""
    return (
        '<section class="ds-opening" data-screen-label="Abertura">'
        '<div class="ds-opening__intro">'
        f'{render_eyebrow("Panorama político")}'
        '<h1 class="ds-opening__title">Quem tem a maioria?</h1>'
        f'<p class="ds-opening__lead">{escape_text(_lead(panorama))}</p>'
        f'<div class="ds-opening__legend">{render_bloc_legend(legend_entries(panorama))}</div>'
        f"</div>{render_rule_explainer(state)}</section>"
    )
