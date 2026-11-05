"""Reusable presentation elements; `*_html` arguments are trusted markup, the rest is escaped."""

from web_components.escaping import escape_text


def render_eyebrow(label, tone=None):
    modifier = f" ds-eyebrow--{tone}" if tone in {"executive", "legislative"} else ""
    return f'<span class="ds-eyebrow{modifier}">{escape_text(label)}</span>'


def render_hero(eyebrow, title, lead):
    return (
        f'<section class="ds-container ds-hero">{render_eyebrow(eyebrow)}'
        f'<h1 class="ds-hero__title">{escape_text(title)}</h1>'
        f'<p class="ds-hero__lead">{escape_text(lead)}</p></section>'
    )


def render_section(section_id, title, body_html, *, eyebrow=None, level=2):
    heading_class = "ds-heading ds-heading--section"
    eyebrow_html = render_eyebrow(eyebrow) if eyebrow else ""
    return (
        f'<section class="ds-section" id="{escape_text(section_id)}">{eyebrow_html}'
        f'<h{level} class="{heading_class}">{escape_text(title)}</h{level}>{body_html}</section>'
    )


def render_card(title, *, eyebrow=None, tone=None, text=None, action_html=""):
    eyebrow_html = render_eyebrow(eyebrow, tone) if eyebrow else ""
    text_html = f'<span class="ds-card__text">{escape_text(text)}</span>' if text else ""
    action = f'<span class="ds-card__action">{action_html}</span>' if action_html else ""
    return (
        f'<article class="ds-card">{eyebrow_html}'
        f'<strong class="ds-card__title">{escape_text(title)}</strong>{text_html}{action}</article>'
    )


def render_card_grid(cards_html):
    return f'<div class="ds-card-grid">{"".join(cards_html)}</div>'


def render_notice(body_html, *, status=False):
    role = ' role="status"' if status else ""
    return f'<div class="ds-notice"{role}>{body_html}</div>'


def render_link_button(label, url, *, primary=False):
    modifier = " ds-button--primary" if primary else ""
    return f'<a class="ds-button{modifier}" href="{escape_text(url)}">{escape_text(label)}</a>'


def render_chip(label, url=None, *, active=False):
    modifier = " ds-chip--active" if active else ""
    if url is None:
        return f'<span class="ds-chip{modifier}">{escape_text(label)}</span>'
    return f'<a class="ds-chip{modifier}" href="{escape_text(url)}">{escape_text(label)}</a>'


def render_tab_links(label, tabs):
    """`tabs` is a sequence of (text, url, selected); navigation is by link, with no script."""
    items = "".join(
        f'<a class="ds-tabs__tab" href="{escape_text(url)}"'
        + (' aria-current="page"' if selected else "")
        + f">{escape_text(text)}</a>"
        for text, url, selected in tabs
    )
    return f'<nav class="ds-tabs" aria-label="{escape_text(label)}">{items}</nav>'


def render_segmented_links(label, options):
    """`options` is a sequence of (text, url, selected)."""
    items = "".join(
        f'<a class="ds-segmented__option" href="{escape_text(url)}"'
        + (' aria-current="true"' if selected else "")
        + f">{escape_text(text)}</a>"
        for text, url, selected in options
    )
    return f'<div class="ds-segmented" role="group" aria-label="{escape_text(label)}">{items}</div>'


def render_disclosure(summary, body_html, *, open_by_default=False):
    opened = " open" if open_by_default else ""
    return (
        f'<details class="ds-disclosure"{opened}><summary>{escape_text(summary)}</summary>'
        f'<div class="ds-disclosure__body">{body_html}</div></details>'
    )
