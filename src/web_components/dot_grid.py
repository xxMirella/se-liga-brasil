"""Grid of equal dots, one per unit (e.g. 100 seats), colored by `ds-bloc--*` classes."""

from web_components.stacked_bar import bloc_class_suffix


def render_dot_grid(bloc_keys):
    """Decorative (aria-hidden): the same information must also be given as text."""
    dots = "".join(f'<span class="ds-bloc--{bloc_class_suffix(key)}"></span>' for key in bloc_keys)
    return f'<div class="ds-dot-grid" aria-hidden="true">{dots}</div>'
