"""Pure geometry of a parliament hemicycle: concentric semicircular rows of seats.

Coordinates are fractions of the semicircle radius (radius 0..1, angle in radians from the right
edge, 0, to the left edge, pi). The layout knows nothing about parties, colors or HTML.
"""

import math
from dataclasses import dataclass

INNER_RADIUS_FRACTION = 0.36
LARGE_CHAMBER_SEAT_COUNT = 200
ROWS_SMALL_CHAMBER = 6
ROWS_LARGE_CHAMBER = 12

# SVG canvas shared with the renderer: 2 : 1.05, the semicircle spans 94 of the 100 half-width.
CANVAS_WIDTH = 200
CANVAS_HEIGHT = 105
SEMICIRCLE_RADIUS = 94
BASELINE_MARGIN = 4


@dataclass(frozen=True)
class SeatPosition:
    angle: float
    radius_fraction: float


@dataclass(frozen=True)
class CanvasPoint:
    x: float
    y: float


def row_count_for(total_seats):
    return ROWS_LARGE_CHAMBER if total_seats > LARGE_CHAMBER_SEAT_COUNT else ROWS_SMALL_CHAMBER


def row_radius_fractions(row_count):
    span = 1 - INNER_RADIUS_FRACTION
    return [INNER_RADIUS_FRACTION + span * index / (row_count - 1) for index in range(row_count)]


def _round_half_up(value):
    return math.floor(value + 0.5)


def seats_per_row(total_seats, radius_fractions):
    """Seats proportional to each row radius; the outer row absorbs the rounding remainder."""
    radius_sum = sum(radius_fractions)
    counts = [_round_half_up(total_seats * radius / radius_sum) for radius in radius_fractions]
    counts[-1] += total_seats - sum(counts)
    return counts


def _angles_for_row(seat_count):
    if seat_count == 1:
        return [math.pi / 2]
    return [math.pi * (1 - index / (seat_count - 1)) for index in range(seat_count)]


def parliament_seat_positions(total_seats):
    """Exactly `total_seats` positions, ordered from the left edge to the right edge by angle."""
    if total_seats <= 0:
        return []
    radius_fractions = row_radius_fractions(row_count_for(total_seats))
    positions = [
        SeatPosition(angle, radius)
        for radius, seat_count in zip(
            radius_fractions, seats_per_row(total_seats, radius_fractions), strict=True
        )
        for angle in _angles_for_row(seat_count)
    ]
    positions.sort(key=lambda seat: (-seat.angle, seat.radius_fraction))
    return positions


def seat_radius_on_canvas(total_seats):
    """Seat radius in canvas units: 4.4% of the width, or 1.9% for large chambers, as diameter."""
    diameter_fraction = 0.019 if total_seats > LARGE_CHAMBER_SEAT_COUNT else 0.044
    return diameter_fraction * CANVAS_WIDTH / 2


def canvas_point(seat):
    x = CANVAS_WIDTH / 2 + SEMICIRCLE_RADIUS * seat.radius_fraction * math.cos(seat.angle)
    height_above_baseline = SEMICIRCLE_RADIUS * seat.radius_fraction * math.sin(seat.angle)
    return CanvasPoint(x, CANVAS_HEIGHT - BASELINE_MARGIN - height_above_baseline)
