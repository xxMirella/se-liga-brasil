"""Stacked bar drawn as a one-row table: `<col width>` sets exact widths without inline styles."""

from dataclasses import dataclass

from web_components.escaping import escape_text

LABEL_MIN_PERCENT = 9.0
BAR_SIZES = frozenset({"sm", "md", "lg"})


def bloc_class_suffix(bloc_key):
    """`far_right` -> `far-right`: the suffix of the `ds-bloc--*` color class."""
    return escape_text(bloc_key).replace("_", "-")


@dataclass(frozen=True)
class BarSegment:
    bloc_key: str  # selects the color class `ds-bloc--<key>`
    percent: float  # share of the whole, 0-100
    text: str = ""  # shown inside the segment only when it is wide enough


def _segment_text(segment):
    return escape_text(segment.text) if segment.percent >= LABEL_MIN_PERCENT else ""


def render_stacked_bar(segments, label, *, size="md", half_marker=False):
    """`half_marker` draws the dashed line at 50% (the majority threshold)."""
    size = size if size in BAR_SIZES else "md"
    visible = [segment for segment in segments if segment.percent > 0]
    show_text = len(visible) > 1  # a lone full segment would sit under the 50% marker
    columns = "".join(f'<col width="{segment.percent:.2f}%">' for segment in visible)
    cells = "".join(
        f'<td class="ds-bloc--{bloc_class_suffix(segment.bloc_key)}">'
        f"{_segment_text(segment) if show_text else ''}</td>"
        for segment in visible
    )
    marker = " ds-stacked-bar--half" if half_marker else ""
    return (
        f'<div class="ds-stacked-bar ds-stacked-bar--{size}{marker}">'
        f'<table role="img" aria-label="{escape_text(label)}"><colgroup>{columns}</colgroup>'
        f"<tr>{cells}</tr></table></div>"
    )
