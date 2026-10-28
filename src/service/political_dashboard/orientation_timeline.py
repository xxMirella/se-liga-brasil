"""Aggregate dated party classifications without projecting the largest party's category."""

from collections import Counter

from service.political_dashboard.political_orientation_catalog import classify_political_orientation
from service.political_dashboard.timeline import executive_party_records

ORIENTATION_COLORS = {
    "left": "#57866d", "center": "#b0a34a", "right": "#c79f53",
    "far_right": "#9b623b",
    "undetermined": "#8c9990", "controversial": "#9d8ca2", "unaffiliated": "#aeb9aa",
}
ORIENTATION_LABELS = {
    "left": "Esquerda", "center": "Centro", "right": "Direita",
    "far_right": "Extrema direita",
    "undetermined": "Sem classificação", "controversial": "Classificação controversa",
    "unaffiliated": "Sem filiação",
}


def orientation_cell(institution, year, kind):
    if kind == "executive":
        return executive_orientation_cell(institution, year)
    from service.political_dashboard.orientation_composition import group_orientation_category
    from service.political_dashboard.senate_orientation_2026 import (
        senate_orientation_cell,
        senate_orientation_summary,
    )

    counts = Counter()
    for group in institution.get("political_parties", []):
        category = group_orientation_category(group, year, institution.get("institution_code"))
        counts[category] += group.get("count", 0)
    missing = (institution.get("total") or 0) - sum(counts.values())
    if missing > 0:
        counts["undetermined"] += missing
    summary = senate_orientation_summary(institution, year, counts)
    if summary:
        return senate_orientation_cell(summary)
    if not counts:
        return category_cell(["undetermined"], "unknown")
    maximum = max(counts.values())
    leaders = sorted(category for category, count in counts.items() if count == maximum)
    state = "mixed" if len(leaders) > 1 else "partial"
    cell = category_cell(leaders, state)
    ideological_counts = sorted((counts[key] for key in ("left", "center", "right")), reverse=True)
    unresolved = sum(counts[key] for key in ("undetermined", "controversial", "unaffiliated"))
    if (len(leaders) == 1 and leaders[0] in {"left", "center", "right"}
            and maximum <= ideological_counts[1] + unresolved):
        cell["label"] += " · liderança incerta"
        cell["color"] = ORIENTATION_COLORS["undetermined"]
    cell["detail"] = (
        "Maior grupo documentado: " + str(maximum) + " de " + str(sum(counts.values()))
        + "; pluralidade não significa maioria absoluta. Registros sem classificação "
        + "e sem filiação são mantidos separados. "
        + "; ".join(f"{ORIENTATION_LABELS[key]}: {counts[key]}" for key in sorted(counts))
    )
    return cell


def executive_orientation_cell(institution, year):
    from service.political_dashboard.executive_orientation_presentation import (
        documented_executive_cell,
    )

    documented = documented_executive_cell(institution, year)
    if documented:
        return documented
    records, _ = executive_party_records(institution)
    categories = set()
    for record in records:
        political_party = record.get("political_party")
        if not str(record.get("political_party_status", "")).startswith("verified_"):
            categories.add("undetermined")
        else:
            categories.add(classify_political_orientation(political_party, year)["category"])
    if not categories:
        categories.add("undetermined")
    cell = category_cell(sorted(categories), "mixed" if len(categories) > 1 else "partial")
    cell["detail"] = (
        "Classificação dos partidos documentados no ano; não avalia toda a atuação do governo."
    )
    return cell


def category_cell(categories, state):
    label = " / ".join(ORIENTATION_LABELS[category] for category in categories)
    color = ORIENTATION_COLORS[categories[0]] if len(categories) == 1 else "#9d8ca2"
    qualifier = "mais de uma classificação documentada" if state == "mixed" else "cobertura parcial"
    return {"label": label, "color": color, "state": state, "qualifier": qualifier}


def render_orientation_annual_summary(data):
    if data.get("view") != "political_orientation":
        return ""
    from service.political_dashboard.executive_orientation_presentation import (
        render_orientation_evidence_sources,
    )
    from service.political_dashboard.timeline import timeline_cell, timeline_series
    from service.public_profile_web.security import text

    year = int(data.get("year", data["as_of"][:4]))
    row = next((row for row in data.get("history", []) if row["year"] == year), {"year": year})
    items = []
    for code, label, kind in timeline_series(data):
        cell = timeline_cell(row, code, kind, "political_orientation")
        detail = text(cell.get("detail", "Sem classificação datada disponível."))
        items.append(f'<li><strong>{text(label)}: {text(cell["label"])}</strong>'
                     f'<p>{detail}</p>{render_orientation_evidence_sources(cell)}</li>')
    return (f'<details class="panorama-orientation-year" open><summary>'
            f'Abordagens documentadas em {year}</summary><ul>{"".join(items)}</ul></details>')
