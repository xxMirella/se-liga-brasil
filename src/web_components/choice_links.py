"""Single-choice groups made of links: the state lives in the URL, so no script is needed."""

from dataclasses import dataclass

from web_components.bloc_legend import render_bloc_swatch
from web_components.escaping import escape_text
from web_components.stacked_bar import bloc_class_suffix

CHOICE_VARIANTS = frozenset({"segmented", "pill", "option", "swatch"})


@dataclass(frozen=True)
class ChoiceLink:
    label: str
    url: str
    selected: bool = False
    bloc_key: str | None = None  # `swatch` variant: color of the square and of the selected tint


def _render_choice(choice, variant):
    classes = "ds-choice"
    if variant == "swatch" and choice.bloc_key:
        classes += f" ds-bloc-scope--{bloc_class_suffix(choice.bloc_key)}"
    current = ' aria-current="true"' if choice.selected else ""
    swatch = render_bloc_swatch(choice.bloc_key) if variant == "swatch" and choice.bloc_key else ""
    return (
        f'<a class="{classes}" href="{escape_text(choice.url)}"{current}>'
        f"{swatch}{escape_text(choice.label)}</a>"
    )


def render_choice_links(label, choices, *, variant="pill"):
    """Variants: `segmented` (joined bar), `pill`, `option` (rounded rectangle), `swatch`."""
    variant = variant if variant in CHOICE_VARIANTS else "pill"
    items = "".join(_render_choice(choice, variant) for choice in choices)
    return (
        f'<div class="ds-choice-group ds-choice-group--{variant}" role="group" '
        f'aria-label="{escape_text(label)}">{items}</div>'
    )
