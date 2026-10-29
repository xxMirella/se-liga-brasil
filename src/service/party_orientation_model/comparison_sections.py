"""Extra report sections: extreme labels, category changes, partial evidence, sensitivity."""

from service.party_orientation_model.contracts import (
    CATEGORY_EXTREME_LEFT,
    CATEGORY_EXTREME_RIGHT,
    CATEGORY_RADICAL_LEFT,
    CATEGORY_RADICAL_RIGHT,
)

EXTREME_CATEGORIES = (CATEGORY_EXTREME_LEFT, CATEGORY_EXTREME_RIGHT)
INTENSE_CATEGORIES = (CATEGORY_RADICAL_LEFT, CATEGORY_RADICAL_RIGHT)


def extreme_label_section(documents: list[dict]) -> list[str]:
    lines = ["## Rótulos extremos e radicais (proposta; aguarda revisão humana)", ""]
    flagged = [d for d in documents if d["category"] in (*EXTREME_CATEGORIES, *INTENSE_CATEGORIES)]
    if not flagged:
        return [
            *lines,
            "Nenhum: nenhuma combinação partido-período atingiu uma dessas categorias.",
            "",
        ]
    lines += ["| Partido | Período | Categoria | Escore | Situação |", "|---|---|---|---|---|"]
    for document in flagged:
        status = (
            "proposta, aguarda revisão humana"
            if document["category"] in EXTREME_CATEGORIES
            else "intensidade sem portão democrático"
        )
        lines.append(
            f"| {document['political_party']} | {document['period']['period_id']} "
            f"| {document['category_label']} | {document['overall_score']:+.2f} | {status} |"
        )
    return [*lines, ""]


def changed_category_section(outcome_rows: list[tuple[dict, str]]) -> list[str]:
    changed = [(d, o) for d, o in outcome_rows if o in ("disagree", "mixed")]
    lines = ["## Partidos que mudariam de categoria em relação ao catálogo", ""]
    if not changed:
        return [*lines, "Nenhum: sem classificação suficiente do modelo, nada muda.", ""]
    lines += ["| Partido | Período | Modelo | Resultado |", "|---|---|---|---|"]
    lines += [
        f"| {d['political_party']} | {d['period']['period_id']} | {d['category_label']} | {o} |"
        for d, o in changed
    ]
    return [*lines, ""]


def _indicative(dimension: dict) -> str:
    score = dimension["indicative_score_not_for_use"]
    if score is None:
        return "—"
    return f"{score:+.2f} ({dimension['indicator_count']} ind., {dimension['evidence_count']} it.)"


def partial_evidence_section(documents: list[dict]) -> list[str]:
    """Insufficient combinations with some scoring evidence; scores are NOT for use."""
    rows = [
        d
        for d in documents
        if d["category"] == "insufficient_evidence"
        and any(dim["indicative_score_not_for_use"] is not None for dim in d["dimensions"].values())
    ]
    lines = [
        "## Evidência parcial (indicativa, NÃO usar como classificação)",
        "",
        "Mínimos da rubrica: 4 indicadores econômicos, 3 socioculturais, 6 itens e 2 fontes por "
        "dimensão. Escores abaixo existem só como transparência.",
        "",
        "| Partido | Período | Econômica | Sociocultural | Motivos |",
        "|---|---|---|---|---|",
    ]
    for d in rows:
        reasons = sorted(
            {r for dim in d["dimensions"].values() for r in dim["insufficiency_reasons"]}
        )
        lines.append(
            f"| {d['political_party']} | {d['period']['period_id']} "
            f"| {_indicative(d['dimensions']['economic'])} "
            f"| {_indicative(d['dimensions']['sociocultural'])} | {', '.join(reasons)} |"
        )
    return [*lines, "", f"{len(rows)} combinações com evidência parcial.", ""]


def sensitivity_section(results: list[dict]) -> list[str]:
    lines = [
        "## Sensibilidade aos pesos das classes (comportamento / declarações / externas)",
        "",
        "Base 70/20/10. As estimativas externas têm peso 0 no motor (calibração); a classe só "
        "varia nominalmente. Declarações só pontuam se houver itens econômicos ou socioculturais "
        "de discurso, que não foram convertidos.",
        "",
        "| Cenário | Combinações | Categoria muda | Classificadas na base |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {r['scenario']} | {r['combinations']} | {r['changed']} | {r['classified_in_base']} |"
        for r in results
    ]
    return [*lines, ""]
