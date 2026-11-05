"""Pure hemicycle geometry and its SVG chart."""

import math
import re

import pytest

from web_components.parliament_chart import SeatGroup, render_parliament_chart, seat_fills
from web_components.parliament_layout import (
    canvas_point,
    parliament_seat_positions,
    row_count_for,
    row_radius_fractions,
    seat_radius_on_canvas,
    seats_per_row,
)


@pytest.mark.parametrize("total", [1, 2, 7, 81, 200, 201, 513])
def test_exactly_total_seats_and_rows_add_up(total):
    assert len(parliament_seat_positions(total)) == total
    radii = row_radius_fractions(row_count_for(total))
    assert sum(seats_per_row(total, radii)) == total


def test_row_counts_and_radii_follow_prototype():
    assert row_count_for(81) == 6 and row_count_for(513) == 12
    radii = row_radius_fractions(6)
    assert radii[0] == pytest.approx(0.36) and radii[-1] == pytest.approx(1.0)


def test_seats_are_ordered_left_to_right_by_angle():
    angles = [seat.angle for seat in parliament_seat_positions(81)]
    assert angles == sorted(angles, reverse=True)


def test_no_gross_overlap_between_seats():
    for total in (81, 513):
        radius = seat_radius_on_canvas(total)
        points = [canvas_point(seat) for seat in parliament_seat_positions(total)]
        closest = min(
            math.dist((a.x, a.y), (b.x, b.y))
            for index, a in enumerate(points) for b in points[index + 1:]
        )
        assert closest > radius * 1.0, (total, closest, radius)


def test_points_stay_inside_the_canvas():
    for seat in parliament_seat_positions(513):
        point = canvas_point(seat)
        assert 0 <= point.x <= 200 and 0 <= point.y <= 105


def test_no_seats_for_zero():
    assert parliament_seat_positions(0) == []


def test_seat_fills_dim_everything_outside_the_highlight():
    groups = [SeatGroup("PAA", "left", 2, "red"), SeatGroup("PBA", "center", 1, "gold")]
    assert seat_fills(groups) == ["red", "red", "gold"]
    assert seat_fills(groups, "PBA") == ["#e6e2d9", "#e6e2d9", "gold"]
    assert seat_fills(groups, "left") == ["red", "red", "#e6e2d9"]


def test_chart_has_one_circle_per_seat_and_no_inline_style():
    groups = [SeatGroup("left", "left", 30, "red"), SeatGroup("right", "right", 51, "blue")]
    html = render_parliament_chart(groups, 81, 41, "Senado: 81 cadeiras")
    assert len(re.findall(r"<circle cx=\"[\d.]+\" cy=\"[\d.]+\" r=\"[\d.]+\" fill=", html)) == 81
    assert 'viewBox="0 0 200 105"' in html and "maioria: 41 de 81" in html
    assert " style=" not in html and "<script" not in html
    assert html.count('fill="red"') == 30 and html.count('fill="blue"') == 51
