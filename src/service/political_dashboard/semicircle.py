"""Accessible SVG indicator geometry scales to historical rolls and the 513-member chamber."""

from math import ceil, cos, pi, sin, sqrt

from service.political_dashboard.composition_charts import (
    composition_group_color,
    ranked_political_groups,
)
from service.political_dashboard.political_palette import UNKNOWN_COLOR
from service.public_profile_web.security import text


def indicator_positions(total):
    rows = 4 if 16 <= total <= 200 else max(1, min(10, ceil(sqrt(total) / 2.8)))
    radii = [65 + index * 95 / max(rows - 1, 1) for index in range(rows)]
    allocations = [int(total * radius / sum(radii)) for radius in radii]
    for index in range(total - sum(allocations)):
        allocations[-1 - index % rows] += 1
    positions = []
    for radius, count in zip(radii, allocations, strict=True):
        for index in range(count):
            angle = pi * index / (count - 1) if count > 1 else pi / 2
            positions.append((angle, 180 - cos(angle) * radius, 174 - sin(angle) * radius))
    return sorted(positions), max(1.4, min(5.3, 46 / sqrt(total)))


def indicator_colors(composition):
    colors = []
    for group in ranked_political_groups(composition):
        color = composition_group_color(group)
        colors.extend([color] * max(0, int(group["count"])))
    return colors


def render_people_semicircle(composition):
    total = composition.get("total") or 0
    if not total:
        rings = "".join(
            f'<path d="M{180 - radius} 174 A{radius} {radius} 0 0 1 {180 + radius} 174" '
            'fill="none" stroke="#dce5df" stroke-width="6" stroke-dasharray="0.1 14" '
            'stroke-linecap="round"/>'
            for radius in (65, 97, 128, 160)
        )
        return (
            '<svg class="panorama-semicircle panorama-semicircle-empty" viewBox="0 0 360 190" '
            'role="img" aria-label="Composição ainda não documentada"><title>Composição ainda não '
            f"documentada</title>{rings}</svg>"
        )
    positions, radius = indicator_positions(total)
    colors = indicator_colors(composition)
    circles = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" '
        f'fill="{colors[index] if index < len(colors) else UNKNOWN_COLOR}"/>'
        for index, (_, x, y) in enumerate(positions)
    )
    label = f"{total} {composition.get('count_label', 'pessoas na composição observada')}"
    count_label = (
        "em exercício" if composition.get("presentation_basis") == "snapshot"
        and composition.get("composition_view") != "political_orientation" else "documentados"
    )
    center = (
        '<text x="180" y="151" text-anchor="middle" class="panorama-indicator-total">'
        f"{total}</text>"
        f'<text x="180" y="174" text-anchor="middle" class="panorama-indicator-label">'
        f"{count_label}</text>"
    )
    return (
        f'<svg class="panorama-semicircle" viewBox="0 0 360 190" role="img" '
        f'aria-label="{text(label)}"><title>{text(label)}</title>{circles}{center}</svg>'
    )
