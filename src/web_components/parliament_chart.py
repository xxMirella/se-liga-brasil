"""Hemicycle chart in SVG: one `<circle>` per seat, colored by attributes (no inline style)."""

from dataclasses import dataclass

from web_components.escaping import escape_text
from web_components.parliament_layout import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    canvas_point,
    parliament_seat_positions,
    seat_radius_on_canvas,
)

DIMMED_SEAT_FILL = "#e6e2d9"


@dataclass(frozen=True)
class SeatGroup:
    group_key: str  # a political party abbreviation or a bloc key; matched by `highlight`
    bloc_key: str
    seat_count: int
    fill: str  # any SVG color


def seat_fills(groups, highlight=None):
    """One fill per seat, left to right. Seats of groups outside the highlight are dimmed.

    If the groups hold fewer seats than requested the last group fills the rest, as the layout
    must always draw every seat of the chamber.
    """
    fills = []
    for group in groups:
        lit = highlight is None or highlight in (group.group_key, group.bloc_key)
        fills.extend([group.fill if lit else DIMMED_SEAT_FILL] * group.seat_count)
    return fills


def _fills_for_total(groups, total_seats, highlight):
    fills = seat_fills(groups, highlight)
    if not fills:
        return [DIMMED_SEAT_FILL] * total_seats
    fills.extend(fills[-1:] * (total_seats - len(fills)))
    return fills[:total_seats]


def _render_seat(position, radius, fill):
    point = canvas_point(position)
    return (
        f'<circle cx="{point.x:.2f}" cy="{point.y:.2f}" r="{radius:g}" '
        f'fill="{escape_text(fill)}"/>'
    )


def render_parliament_chart(
    groups, total_seats, majority_threshold, description, *, highlight=None
):
    """Semicircle scaled by `viewBox`, dashed center line and the 'maioria' label."""
    radius = seat_radius_on_canvas(total_seats)
    fills = _fills_for_total(groups, total_seats, highlight)
    circles = "".join(
        _render_seat(position, radius, fill)
        for position, fill in zip(parliament_seat_positions(total_seats), fills, strict=True)
    )
    return (
        f'<div class="ds-parliament" role="img" aria-label="{escape_text(description)}">'
        f'<svg class="ds-parliament__seats" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" '
        f'aria-hidden="true" focusable="false">{circles}</svg>'
        f'<span class="ds-parliament__majority">maioria: {majority_threshold} '
        f"de {total_seats}</span></div>"
    )
