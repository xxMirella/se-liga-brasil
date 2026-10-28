"""Classify only dated party observations; ideological estimates are not government actions."""

import json
from functools import lru_cache
from math import isfinite
from pathlib import Path

ORIENTATION_METHODOLOGY_URL = "https://doi.org/10.7910/DVN/MFIXKW"
ORIENTATION_METHODOLOGY_LABEL = "Survey de especialistas: observações de 2018 e 2022"
ORIENTATION_CATALOG_VERSION = "2026-10-27.1"
CATEGORY_LABELS = {
    "left": "Esquerda", "center": "Centro", "right": "Direita",
    "undetermined": "Sem classificação", "controversial": "Classificação controversa",
    "unaffiliated": "Sem filiação",
}
UNAFFILIATED_LABELS = frozenset({"s/partido", "sem partido", "sem filiação partidária"})
LIMITATION = (
    "Estimativa nacional da posição do partido no ano pesquisado; não classifica ações "
    "individuais, governos, coalizões ou todo o período de existência do partido. "
    "Não há interpolação nem herança automática de siglas renomeadas."
)
THRESHOLD_RULE = (
    "Agrupamento do site da média original de 0 a 10: esquerda <4,5; "
    "centro de 4,5 a 5,5 inclusive; direita >5,5. Não são três categorias originais do survey."
)


@lru_cache(maxsize=1)
def orientation_index():
    source = Path(__file__).with_suffix(".json")
    catalog = json.loads(source.read_text())
    if catalog.get("schema_version") != "dated_political_orientation_catalog.v1":
        raise ValueError("POLITICAL_ORIENTATION_CATALOG_SCHEMA_NOT_SUPPORTED")
    if catalog.get("version") != ORIENTATION_CATALOG_VERSION:
        raise ValueError("POLITICAL_ORIENTATION_CATALOG_VERSION_MISMATCH")
    indexed = {}
    for row in catalog["observations"]:
        for year in range(row["year_start"], row["year_end"] + 1):
            key = (row["political_party"].casefold(), year)
            indexed.setdefault(key, []).append(row)
    return indexed


def score_category(score):
    if isinstance(score, bool) or not isfinite(score) or not 0 <= score <= 10:
        raise ValueError("POLITICAL_ORIENTATION_SCORE_OUTSIDE_SCALE")
    if score < 4.5:
        return "left"
    return "center" if score <= 5.5 else "right"


def orientation_result(category, status, **evidence):
    return {"category": category, "label": CATEGORY_LABELS[category], "status": status,
            "catalog_version": ORIENTATION_CATALOG_VERSION, "limitation": LIMITATION,
            "threshold_rule": THRESHOLD_RULE, "methodology_id": None,
            "source_url": None, "reference_year": None, "score": None, **evidence}


def classify_orientation_observations(observations):
    if not observations:
        return orientation_result("undetermined", "no_dated_classification")
    categories = {score_category(row["score"]) for row in observations}
    if len(categories) != 1:
        return orientation_result("controversial", "conflicting_sources",
                                  sources=[dict(row) for row in observations])
    row = observations[0]
    return orientation_result(categories.pop(), "classified", **{
        key: row[key] for key in (
            "methodology_id", "source_url", "reference_year", "score", "respondents",
            "respondent_standard_deviation",
        )
    })


def classify_political_orientation(political_party, year):
    label = str(political_party or "").strip().casefold()
    if label in UNAFFILIATED_LABELS:
        return orientation_result("unaffiliated", "not_a_party")
    return classify_orientation_observations(orientation_index().get((label, year), []))
