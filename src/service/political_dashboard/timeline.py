"""Annual party bands keep geography fixed and never manufacture undocumented majorities."""

from itertools import groupby
from urllib.parse import urlencode

from service.political_dashboard.composition_charts import is_political_party
from service.political_dashboard.historical_events import (
    historical_context_height,
    render_historical_event_sources,
    render_historical_events,
)
from service.political_dashboard.political_palette import (
    MIXED_COLOR,
    UNKNOWN_COLOR,
    political_party_color,
)
from service.political_dashboard.presidential_explanations import render_presidential_markers
from service.public_profile_web.security import text

TIMELINE_START_YEAR = 1880


def timeline_series(data):
    if data["level"] == "federal":
        return [("senado", "Senado", "legislative"),
                ("presidency", "Presidência", "executive"),
                ("camara", "Câmara dos Deputados", "legislative")]
    if data["level"] == "municipal":
        return [("municipal_government", "Prefeitura", "executive"),
                ("municipal_council", "Câmara Municipal", "legislative")]
    government = "district_government" if data["uf"] == "DF" else "state_government"
    assembly = data["assembly"].get("institution_code") or "state_assembly"
    return [("senado", "Senado · " + data["uf"], "legislative"),
            (government, "Governo estadual", "executive"),
            (assembly, "Assembleia Legislativa", "legislative")]


def timeline_year_url(data, year):
    parameters = {"territory": "BR" if data["level"] == "federal" else data["uf"],
                  "year": year}
    if data.get("municipality_ibge"):
        parameters["municipality_ibge"] = data["municipality_ibge"]
    if data.get("view") == "political_orientation":
        parameters["view"] = "political_orientation"
    return "/panorama?" + urlencode(parameters) + "#panorama-results"


def timeline_institution(row, code):
    for institution in row.get("institutions", []):
        if institution["institution_code"] == code:
            return institution
        if code == "state_assembly" and set(institution.get("office_kinds") or []) & {
            "state_deputy", "district_deputy"
        }:
            return institution
    return None


def timeline_cell(row, code, kind, view="political_party"):
    if view == "political_orientation":
        from service.political_dashboard.orientation_historical_context import (
            documented_legislative_absence,
        )

        absence = documented_legislative_absence(code, row["year"])
        if absence:
            return absence
    if row["year"] < 1889 and code == "presidency":
        return {"label": "Monarquia · Presidência ainda não existia",
                "color": UNKNOWN_COLOR, "state": "not_applicable"}
    institution = timeline_institution(row, code)
    if institution is None:
        legacy = {"senado": "senate_observations", "alesp": "assembly_observations",
                  "alerj": "assembly_observations", "presidency": "presidency_observations",
                  "state_government": "government_observations",
                  "municipal_government": "mayoralty_observations",
                  "municipal_council": "municipal_council_observations"}
        available = bool(row.get(legacy.get(code, "")))
        return {"label": "Partido não informado" if available else "Sem dados",
                "color": UNKNOWN_COLOR, "state": "unknown" if available else "missing"}
    if institution.get("institutional_status") == "suspended_whole_year":
        return {"label": "Senado sem funcionamento", "color": UNKNOWN_COLOR,
                "state": "suspended"}
    if view == "political_orientation":
        from service.political_dashboard.orientation_timeline import orientation_cell

        return orientation_cell(institution, row["year"], kind)
    return executive_cell(institution) if kind == "executive" else legislative_cell(institution)


def legislative_cell(institution):
    groups = institution.get("political_parties") or []
    known = [group for group in groups if is_political_party(group) and group.get("count", 0)]
    if not institution.get("total") or not known:
        return {"label": "Partido não informado", "color": UNKNOWN_COLOR, "state": "unknown"}
    maximum = max(group["count"] for group in known)
    leaders = [group["abbreviation"] for group in known if group["count"] == maximum]
    if len(leaders) > 1:
        return {"label": "Empate: " + " / ".join(sorted(leaders)),
                "color": MIXED_COLOR, "state": "mixed"}
    partial = (institution.get("coverage") not in {"observed_complete", "verified_current_roster"}
               or any(not is_political_party(group) for group in groups))
    return {"label": leaders[0], "color": political_party_color(leaders[0]),
            "state": "partial" if partial else "known"}


def executive_party_records(institution):
    current = institution.get("current")
    records = (institution.get("segments") or []) + (
        institution.get("national_observations") or []
    )
    has_periods = any(record.get("political_party_periods") for record in records)
    current_verified = current and str(current.get("political_party_status", "")).startswith(
        "verified_"
    ) and current.get("political_party")
    if current_verified and not has_periods:
        records = [current]
    periods = [period for record in records
               for period in (record.get("political_party_periods") or [record])]
    return periods, bool(current_verified and not has_periods)


def executive_cell(institution):
    records, snapshot = executive_party_records(institution)
    known = [record for record in records if str(record.get("political_party_status", ""))
             .startswith("verified_") and record.get("political_party")]
    parties = sorted({record["political_party"] for record in known})
    if not parties:
        return {"label": "Partido não informado", "color": UNKNOWN_COLOR, "state": "unknown"}
    if len(parties) > 1:
        return {"label": " / ".join(parties), "color": MIXED_COLOR, "state": "mixed"}
    return {"label": parties[0], "color": political_party_color(parties[0]),
            "state": "known" if snapshot else "partial"}


def timeline_cell_description(cell, year):
    coverage = {"partial": "cobertura parcial", "mixed": "mais de um partido no ano",
                "unknown": "partido não informado", "missing": "sem dados",
                "not_applicable": "instituição ainda não existente",
                "suspended": "funcionamento institucional suspenso neste ano"}
    qualifier = cell.get("qualifier", coverage.get(cell["state"]))
    description = f"{year} · {cell['label']}" + (f" · {qualifier}" if qualifier else "")
    return description + (f" · {cell['detail']}" if cell.get("detail") else "")


def render_timeline_cell(cell, data, year, x, y, width):
    description = text(timeline_cell_description(cell, year))
    rectangle = (f'<rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="32" '
                 'fill="transparent"/>')
    if year < TIMELINE_START_YEAR or cell["state"] in {"missing", "not_applicable"}:
        return ""
    return (f'<a href="{text(timeline_year_url(data, year))}" '
            f'aria-label="{description}"><title>{description}</title>{rectangle}</a>')


def timeline_band_runs(cells):
    """Merge consecutive display identities in one pass, independent of coverage flags."""
    return [list(group) for _, group in groupby(enumerate(cells), key=lambda pair: (
        pair[1]["label"], pair[1]["color"],
        pair[1]["state"] in {"missing", "not_applicable"}
    ))]


def render_timeline_run(run, x_start, width, y):
    cell = run[0][1]
    run_width = len(run) * width
    gap = min(3, width * .4)
    x = x_start + run[0][0] * width + gap / 2
    fill = "#edf2ee" if cell["state"] == "missing" else cell["color"]
    rectangle = (f'<rect class="panorama-timeline-band" x="{x:.2f}" y="{y}" '
                 f'width="{run_width - gap:.2f}" height="32" fill="{fill}" rx="3">'
                 f'<title>{text(cell["label"])}</title></rect>')
    label = cell["label"]
    if run_width - gap < max(50, len(label) * 6):
        return rectangle
    midpoint = x_start + (run[0][0] + len(run) / 2) * width
    return rectangle + (f'<text x="{midpoint:.2f}" y="{y + 16}" text-anchor="middle" '
                        'dominant-baseline="middle" class="panorama-band-label">'
                        f'{text(label)}</text>')


def render_timeline_row(cells, data, years, x_start, width, y):
    blocks = "".join(render_timeline_run(run, x_start, width, y)
                     for run in timeline_band_runs(cells))
    annual_links = "".join(render_timeline_cell(cell, data, year, x_start + offset * width,
                                               y, width)
                           for offset, (year, cell) in enumerate(zip(years, cells, strict=True)))
    return blocks + annual_links


def render_timeline_axis(years, x_start, width):
    ticks = {years[0], years[-1]} | {year for year in years if year % 20 == 0}
    return "".join(
        f'<text x="{x_start + (year - years[0] + .5) * width:.2f}" y="23" '
        f'text-anchor="middle">{year}</text>' for year in sorted(ticks)
    )


def render_timeline_bands(data):
    history = [row for row in data.get("history", []) if row["year"] >= TIMELINE_START_YEAR]
    if not history:
        return '<p class="panorama-caption">Histórico ainda não disponível neste recorte.</p>'
    history_by_year = {row["year"]: row for row in history}
    first_year = TIMELINE_START_YEAR
    years = list(range(first_year, max(history_by_year) + 1))
    history = [history_by_year.get(year, {"year": year}) for year in years]
    series = timeline_series(data)
    x_start, plot_width = 155, 1015
    width = plot_width / len(years)
    elements = [render_timeline_axis(years, x_start, width),
                render_historical_events(years[0], years[-1], x_start, width)]
    for index, (code, label, kind) in enumerate(series):
        y = historical_context_height() + index * 58
        cells = [timeline_cell(row, code, kind, data.get("view", "political_party"))
                 for row in history]
        elements.append(f'<text x="0" y="{y + 20}">{text(label)}</text>')
        elements.append(render_timeline_row(cells, data, years, x_start, width, y))
        if code == "presidency":
            elements.append(render_presidential_markers(
                history, years, x_start, width, y, data.get("view", "political_party")
            ))
    selected = data.get("year", int(data["as_of"][:4]))
    height = historical_context_height() + len(series) * 58
    selection = render_timeline_selection(selected, years, x_start, width, height)
    chart_label = (
        "Linha do tempo das abordagens políticas por ano"
        if data.get("view") == "political_orientation"
        else "Linha do tempo dos partidos por ano"
    )
    return f'''<div class="panorama-timeline-scroll"><svg class="panorama-timeline"
viewBox="0 0 1180 {height}" role="group" aria-label="{chart_label}">
{"".join(elements)}{selection}</svg></div>
{render_historical_event_sources()}'''



def render_timeline_selection(selected, years, x_start, width, height):
    if not years[0] <= selected <= years[-1]:
        return ""
    x = x_start + (selected - years[0] + .5) * width
    return (f'<path d="M{x:.2f} {historical_context_height() - 10}V{height - 10}" '
            'stroke="#b89432" stroke-width="2" pointer-events="none"/>'
            f'<text x="{x:.2f}" y="{height - 2}" text-anchor="middle">{selected}</text>')
