"""Comparable legislative bars distinguish the largest group from a majority."""

from service.political_dashboard.political_palette import political_group_color
from service.public_profile_web.security import text

NON_PARTY_LABELS = frozenset({"s/partido", "sem partido", "não informado", "não identificado"})


def composition_group_color(group):
    if category := group.get("orientation_category"):
        from service.political_dashboard.orientation_timeline import ORIENTATION_COLORS

        return ORIENTATION_COLORS[category]
    return political_group_color(group["abbreviation"], identified=is_political_party(group))


def is_political_party(group):
    label = group["abbreviation"].strip().casefold()
    if group.get("political_party_code") in {"unreported", "unknown", "unreconciled"}:
        return False
    return label not in NON_PARTY_LABELS and not label.startswith(
        ("filiação ", "desconhecid", "sem partido", "sem filiação", "não identif", "não informad")
    )


def ranked_political_groups(composition):
    return sorted(
        composition["political_parties"], key=lambda group: (-group["count"], group["abbreviation"])
    )


def render_largest_political_group(groups):
    political_parties = [group for group in groups if is_political_party(group)]
    if not political_parties:
        return ""
    largest = max(group["count"] for group in political_parties)
    leaders = [group["abbreviation"] for group in political_parties if group["count"] == largest]
    title = "Maior bancada documentada" if len(leaders) == 1 else "Maiores bancadas documentadas"
    return (
        f'<p class="panorama-leading-group"><strong>{title}:</strong> '
        f"{text(' · '.join(leaders))} · {largest} pessoas.</p>"
    )


def render_proportional_group(group, maximum, total):
    width = group["count"] / maximum * 100
    percentage = f"{group['count'] / total * 100:.1f}".replace(".", ",")
    category = "" if is_political_party(group) else ' class="panorama-unaffiliated"'
    color = composition_group_color(group)
    return f"""<li{category}><span>{text(group["abbreviation"])}</span>
<span class="panorama-track" aria-hidden="true"><svg viewBox="0 0 100 10"
preserveAspectRatio="none"><rect width="{width:.2f}" height="10" rx="1"
fill="{color}"/></svg></span>
<strong>{group["count"]}<small>{percentage}%</small></strong></li>"""


def render_party_bars(composition, *, compact=False, vertical=False):
    if compact:
        return render_party_legend(composition)
    total = composition["total"]
    groups = ranked_political_groups(composition)
    maximum = max((group["count"] for group in groups), default=0)
    if not total or maximum <= 0:
        return ""
    renderer = render_vertical_group if vertical else render_proportional_group
    bars = "".join(renderer(group, maximum, total) for group in groups)
    chart_class = "panorama-vertical-bars" if vertical else "panorama-bars"
    dimension = "Altura" if vertical else "Comprimento"
    if composition.get("composition_view") == "political_orientation":
        from service.political_dashboard.orientation_composition import (
            render_largest_orientation_group,
        )

        leading = render_largest_orientation_group(groups)
        group_label = "abordagem política"
        largest_label = "Maior grupo"
    else:
        leading = render_largest_political_group(groups)
        group_label = "partido"
        largest_label = "Maior bancada"
    chart = f'<ul class="{chart_class}" aria-label="Pessoas por {group_label}">{bars}</ul>'
    if vertical:
        chart = render_vertical_axes(chart, maximum)
    return (
        leading
        + chart
        + '<details class="panorama-source-notes"><summary>Como ler as barras</summary>'
        + f'<p class="panorama-chart-scale">{dimension} proporcional ao número de pessoas. '
        "A maior contagem ocupa toda a escala; percentuais sobre o total observado. "
        f"{largest_label} não significa maioria absoluta nem base do governo.</p></details>"
    )


def render_vertical_group(group, maximum, total):
    height = group["count"] / maximum * 100
    percentage = f"{group['count'] / total * 100:.1f}".replace(".", ",")
    category = "" if is_political_party(group) else ' class="panorama-unaffiliated"'
    color = composition_group_color(group)
    return f'''<li{category}><span class="panorama-vertical-track" aria-hidden="true">
<svg viewBox="0 0 24 100"
preserveAspectRatio="none"><rect x="3" y="{100 - height:.2f}" width="18"
height="{height:.2f}" rx="1" fill="{color}"/></svg></span>
<strong>{group["count"]}<small>{percentage}%</small></strong>
<span class="panorama-vertical-label">{text(group["abbreviation"])}</span></li>'''



def render_vertical_axes(chart, maximum):
    ticks = "".join(f"<span>{maximum * step / 4:g}</span>" for step in range(4, -1, -1))
    return (
        '<div class="panorama-column-chart" role="group" aria-label="Gráfico de cadeiras">'
        '<span class="panorama-y-title">Cadeiras</span>'
        f'<div class="panorama-y-ticks" aria-hidden="true">{ticks}</div>'
        f'<div class="panorama-column-scroll">{chart}</div>'
        '<p class="panorama-x-title">Partidos ou abordagens políticas · cadeiras e percentual</p>'
        '</div>'
    )


def render_party_legend(composition):
    groups = ranked_political_groups(composition)
    rows = []
    for group in groups:
        color = composition_group_color(group)
        percentage = ""
        if composition.get("composition_view") == "political_orientation" and composition.get(
            "total"
        ):
            share = f"{group['count'] / composition['total'] * 100:.1f}".replace(".", ",")
            percentage = f"<small>{share}%</small>"
        category = "" if is_political_party(group) else ' class="panorama-unaffiliated"'
        rows.append(
            f'<li{category}><svg width="9" height="9" viewBox="0 0 9 9" aria-hidden="true">'
            f'<rect width="9" height="9" rx="4.5" fill="{color}"/></svg>'
            f"<span>{text(group['abbreviation'])}</span><strong>{group['count']}{percentage}</strong></li>"
        )
    group_label = "abordagem política" if composition.get("composition_view") else "partido"
    return (
        f'<ul class="panorama-party-legend" aria-label="Integrantes por {group_label}">'
        + "".join(rows)
        + "</ul>"
    )
