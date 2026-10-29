"""Render the per-party comparison table and the model evidence behind each period."""

from service.party_orientation_comparison.formatting import (
    CONFIDENCE_LABELS,
    DIMENSION_LABELS,
    DIMENSION_STATUS_LABELS,
    LAYER_LABELS,
    count_label,
    format_number,
    localize_decimals,
    reason_label,
)
from service.party_orientation_comparison.rows import (
    GROUP_LABELS,
    OUTCOME_LABELS,
    model_score_on_survey_scale,
)
from service.public_profile_web.security import text

PROPOSAL_NOTE = "proposta, aguarda revisão humana"


def render_survey_cell(survey):
    if not survey:
        return "Sem estimativa neste período"
    items = []
    for entry in survey:
        respondents = f", {entry['respondents']} especialistas" if entry.get("respondents") else ""
        items.append(
            f"<div><strong>{text(GROUP_LABELS[entry['group']])}</strong> em {entry['year']}"
            f"<br>nota {format_number(entry['score'])} de 10{respondents}</div>"
        )
    return "".join(items)


def render_model_score(model):
    score = model["overall_score"]
    if score is None:
        return "sem nota: evidência insuficiente"
    return (
        f"nota {format_number(score, signed=True)} (de {format_number(-1, 0)} a +1), "
        f"equivalente a {format_number(model_score_on_survey_scale(score))} de 10"
    )


def render_model_cell(model):
    if model is None:
        return "O modelo não avaliou esta sigla"
    if model.get("no_evidence"):
        return "<strong>Sem classificação</strong><br>nenhuma evidência no período"
    proposal = (
        f' <span class="comparison-proposal">({PROPOSAL_NOTE})</span>'
        if "extreme" in model["category"]
        else ""
    )
    confidence = CONFIDENCE_LABELS.get(model["confidence_label"], text(model["confidence_label"]))
    return (
        f"<strong>{text(model['category_label'])}</strong>{proposal}<br>"
        f"{render_model_score(model)}<br>confiança {confidence}"
    )


def render_dimension(name, dimension):
    layers = ", ".join(
        f"{LAYER_LABELS.get(layer, text(layer))}: {count}"
        for layer, count in sorted(dimension["layers"].items())
    )
    indicative = (
        ""
        if dimension["indicative_score"] is None or dimension["score"] is not None
        else f"; nota indicativa {format_number(dimension['indicative_score'], signed=True)} "
        "(não usada como classificação)"
    )
    score = (
        f"; nota {format_number(dimension['score'], signed=True)}"
        if dimension["score"] is not None
        else ""
    )
    status = DIMENSION_STATUS_LABELS.get(dimension["status"], text(dimension["status"]))
    return (
        f"<dt>{DIMENSION_LABELS[name]}: {status}</dt>"
        f"<dd>{count_label(dimension['evidence_count'], 'evidência', 'evidências')} em "
        f"{count_label(dimension['indicator_count'], 'indicador', 'indicadores')}"
        f"{score}{indicative}. Camadas: {layers or 'nenhuma'}.</dd>"
    )


def render_model_evidence(model):
    if model is None or model.get("no_evidence"):
        return "—"
    dimensions = "".join(render_dimension(n, d) for n, d in model["dimensions"].items())
    reasons = "; ".join(reason_label(code) for code in model["insufficiency_reasons"])
    explanations = "".join(f"<li>{text(localize_decimals(i))}</li>" for i in model["explanations"])
    markers = "".join(f"<li>{text(marker)}</li>" for marker in model["extreme_markers"])
    return (
        "<details><summary>Ver evidências do modelo</summary>"
        f'<dl class="comparison-evidence">{dimensions}</dl>'
        + (f"<p>Motivos de insuficiência: {reasons}.</p>" if reasons else "")
        + (f"<p>Principais evidências:</p><ul>{explanations}</ul>" if explanations else "")
        + (
            f"<p>Marcadores documentados ({PROPOSAL_NOTE}):</p><ul>{markers}</ul>"
            if markers
            else ""
        )
        + "</details>"
    )


def render_row(row):
    model_note = ""
    if row.model and row.model.get("category") in ("center_left", "center_right"):
        model_note = (
            " Para comparar, centro-esquerda conta como esquerda e centro-direita como direita."
        )
    return (
        f'<tr id="periodo-{text(row.period_id)}">'
        f'<th scope="row">{row.year_start}–{row.year_end}</th>'
        f"<td>{render_survey_cell(row.survey)}</td><td>{render_model_cell(row.model)}</td>"
        f"<td><strong>{OUTCOME_LABELS[row.outcome]}</strong><br>{text(row.reason)}{model_note}</td>"
        f"<td>{render_model_evidence(row.model)}</td></tr>"
    )


def render_comparison_table(political_party, rows, empty_periods):
    body = "".join(render_row(row) for row in rows)
    empty = (
        f"<p>Sem registro de nenhum dos métodos: {', '.join(text(p) for p in empty_periods)}.</p>"
        if empty_periods
        else ""
    )
    return (
        '<div class="comparison-scroll"><table class="comparison-table">'
        f"<caption>{text(political_party)}: pesquisa de especialistas e modelo de atuação, "
        'por período</caption><thead><tr><th scope="col">Período</th>'
        '<th scope="col">Pesquisa de especialistas</th><th scope="col">Modelo de atuação</th>'
        '<th scope="col">Resultado</th><th scope="col">Evidências</th></tr></thead>'
        f"<tbody>{body}</tbody></table></div>{empty}"
    )
