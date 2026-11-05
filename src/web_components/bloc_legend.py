"""Color swatches and legends keyed by bloc (or any category with a `ds-bloc--*` color class)."""

from web_components.escaping import escape_text
from web_components.stacked_bar import bloc_class_suffix

SWATCH_SIZES = frozenset({"sm", "md"})


def render_bloc_swatch(bloc_key, *, size="md", round_shape=False):
    """Small color square (12px `sm`, 14px `md`) or circle; the color comes from a CSS class."""
    size = size if size in SWATCH_SIZES else "md"
    shape = " ds-swatch--round" if round_shape else ""
    return (
        f'<span class="ds-swatch ds-swatch--{size}{shape} '
        f'ds-bloc--{bloc_class_suffix(bloc_key)}" aria-hidden="true"></span>'
    )


def render_bloc_legend(entries, *, compact=False, half_marker_label=None):
    """`entries` is a sequence of (bloc_key, label); `half_marker_label` adds the dashed key."""
    size = "sm" if compact else "md"
    items = "".join(
        f'<span class="ds-legend__item">{render_bloc_swatch(key, size=size)}'
        f"{escape_text(label)}</span>"
        for key, label in entries
    )
    if half_marker_label:
        items += (
            '<span class="ds-legend__item"><span class="ds-legend__half-line" '
            f'aria-hidden="true"></span>{escape_text(half_marker_label)}</span>'
        )
    modifier = " ds-legend--compact" if compact else ""
    return f'<div class="ds-legend{modifier}">{items}</div>'
