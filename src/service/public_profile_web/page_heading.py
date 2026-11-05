"""Page heading with a plain <h1>: eyebrow, title and lead. Candidate for web_components."""

from web_components import render_eyebrow
from web_components.escaping import escape_text


def render_page_heading(eyebrow, title, lead):
    return (
        f'<header class="page-heading">{render_eyebrow(eyebrow)}'
        f"<h1>{escape_text(title)}</h1>"
        f'<p class="page-heading__lead">{escape_text(lead)}</p></header>'
    )
