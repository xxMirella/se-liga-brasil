"""Portuguese number and label formatting for the comparison page."""

import re

from service.public_profile_web.security import text

MINUS = "−"
CONFIDENCE_LABELS = {"low": "baixa", "medium": "média", "high": "alta"}
DIMENSION_LABELS = {"economic": "Econômica", "sociocultural": "Sociocultural"}
DIMENSION_STATUS_LABELS = {
    "sufficient": "classificada",
    "insufficient_evidence": "evidência insuficiente",
}
LAYER_LABELS = {
    "votes": "votos",
    "implemented_policies": "políticas implementadas",
    "supported_policies": "políticas apoiadas",
    "bills": "projetos apresentados",
    "thematic_focus": "foco temático",
    "discourse": "discurso",
    "expert_survey": "pesquisa de especialistas",
}
REASON_LABELS = {
    "too_few_evidence_items": "poucos itens de evidência",
    "too_few_distinct_indicators": "poucos indicadores distintos",
    "too_few_distinct_sources": "poucas fontes distintas",
    "no_scoring_evidence": "nenhuma evidência utilizável no cálculo",
    "confidence_below_minimum": "confiança abaixo do mínimo",
    "required_dimension_insufficient:economic": "dimensão econômica insuficiente",
    "required_dimension_insufficient:sociocultural": "dimensão sociocultural insuficiente",
}


def format_number(value, digits=2, *, signed=False):
    rendered = f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"
    return rendered.replace("-", MINUS).replace(".", ",")


def localize_decimals(sentence):
    decimals = re.sub(r"(?<=\d)\.(?=\d)", ",", sentence)
    return re.sub(r"(?<![\w-])-(?=\d)", MINUS, decimals)


def reason_label(code):
    return REASON_LABELS.get(code) or text(code)


def count_label(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"
