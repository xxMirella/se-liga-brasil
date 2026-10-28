"""Preserve geographical and annual context when switching timeline classifications."""

from service.public_profile_web.security import text


def render_timeline_view_filter(data):
    selected = data.get("view", "political_party")
    parameters = {
        "territory": "BR" if data["level"] == "federal" else data["uf"],
        "year": data.get("year", data["as_of"][:4]),
    }
    if data.get("municipality_ibge"):
        parameters["municipality_ibge"] = data["municipality_ibge"]
    hidden = "".join(f'<input type="hidden" name="{key}" value="{text(value)}">'
                     for key, value in parameters.items())
    options = "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{label}</option>'
        for value, label in [("political_party", "Partido"),
                             ("political_orientation", "Abordagem política")]
    )
    return f'''<form class="panorama-filters panorama-view-filter" method="get"
action="/panorama#panorama-results" aria-label="Visualização da composição e linha do tempo">
{hidden}<label>Visualizar composição e linha do tempo por
<select name="view">{options}</select></label>
<button type="submit">Atualizar visualização</button></form>'''


def render_orientation_legend(data):
    if data.get("view") != "political_orientation":
        return ""
    from service.political_dashboard.orientation_timeline import (
        ORIENTATION_COLORS,
        ORIENTATION_LABELS,
    )
    legend = "".join(
        f'<span><svg width="12" height="12" aria-hidden="true">'
        f'<rect width="12" height="12" rx="2" fill="{color}"/></svg> '
        f'{text(ORIENTATION_LABELS[category])}</span>'
        for category, color in ORIENTATION_COLORS.items()
    )

    return f'''<div class="panorama-orientation-legend"
aria-label="Legenda das abordagens políticas">
{legend}</div>'''
