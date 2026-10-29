"""Compare model documents with the current catalog and render the Markdown report."""

from collections.abc import Callable
from dataclasses import dataclass

from service.party_orientation_model.catalog_adapter import catalog_group
from service.party_orientation_model.comparison_sections import (
    changed_category_section,
    extreme_label_section,
    partial_evidence_section,
    sensitivity_section,
)
from service.party_orientation_model.contracts import normalize_party_key

DEFAULT_HYPOTHESES: dict[str, str] = {}
HIGHLIGHTED_PARTIES = ("PDT", "PCdoB")  # shown for scrutiny; no expected result is assumed
GROUP_LABELS = {
    "left": "esquerda",
    "center": "centro",
    "right": "direita",
    "undetermined": "sem classificação",
    "controversial": "controversa",
    "mixed": "perfil misto",
}
OUTCOME_LABELS = {
    "agree": "concorda",
    "disagree": "discorda",
    "mixed": "parcial",
    "not_comparable": "não comparável",
}
CatalogLookup = Callable[[str, int], str]  # (political_party, year) -> catalog category


@dataclass(frozen=True)
class Comparison:
    document: dict
    catalog_by_year: dict[int, str]
    outcome: str


def compare_document(document: dict, lookup: CatalogLookup) -> Comparison:
    period = document["period"]
    by_year = {
        year: lookup(document["political_party"], year)
        for year in range(period["year_start"], period["year_end"] + 1)
    }
    return Comparison(document, by_year, _outcome(catalog_group(document["category"]), by_year))


def _outcome(model_group: str, by_year: dict[int, str]) -> str:
    known = [group for group in by_year.values() if group in ("left", "center", "right")]
    if model_group not in ("left", "center", "right") or not known:
        return "not_comparable"
    matches = sum(1 for group in known if group == model_group)
    if matches == len(known):
        return "agree"
    return "disagree" if matches == 0 else "mixed"


def _catalog_text(by_year: dict[int, str]) -> str:
    known = {
        year: GROUP_LABELS.get(group, group)
        for year, group in by_year.items()
        if group in ("left", "center", "right")
    }
    return (
        ", ".join(f"{year}: {label}" for year, label in sorted(known.items())) or "sem observação"
    )


def _score_text(document: dict) -> str:
    score = document["overall_score"]
    return "n/d" if score is None else f"{score:+.2f}"


def _row(comparison: Comparison) -> str:
    document = comparison.document
    return (
        f"| {document['political_party']} | {document['period']['period_id']} "
        f"| {document['category_label']} | {_score_text(document)} "
        f"| {document['confidence_label']} "
        f"| {_catalog_text(comparison.catalog_by_year)} | {OUTCOME_LABELS[comparison.outcome]} |"
    )


def _highlight(party: str, comparisons: list[Comparison], hypotheses: dict[str, str]) -> list[str]:
    own = [c for c in comparisons if c.document["political_party_id"] == normalize_party_key(party)]
    lines = [f"### {party}", ""]
    if not own:
        return lines + [
            "O modelo ainda não tem evidência aplicável: nenhuma conclusão é emitida.",
            "",
        ]
    for comparison in own:
        lines += _highlight_period(comparison, hypotheses.get(party))
    return [*lines, ""]


def _highlight_period(comparison: Comparison, hypothesis: str | None) -> list[str]:
    document = comparison.document
    lines = [
        f"- Período {document['period']['period_id']}: **{document['category_label']}** "
        f"(escore {_score_text(document)}, confiança {document['confidence_label']}, "
        f"{len(document['evidence_used'])} evidências); "
        f"catálogo: {_catalog_text(comparison.catalog_by_year)}."
    ]
    if hypothesis:
        lines.append(
            f"  - Hipótese registrada: {GROUP_LABELS[hypothesis]}; "
            f"{_hypothesis_verdict(document, hypothesis)}"
        )
    lines.extend(
        f"  - Divergência discurso x ação: {d['explanation']}" for d in document["divergences"]
    )
    lines.extend(f"  - {text}" for text in document["explanation_summary"])
    return lines


def _hypothesis_verdict(document: dict, hypothesis: str) -> str:
    group = catalog_group(document["category"])
    if group not in ("left", "center", "right"):
        return "o modelo não classificou; a evidência atual não confirma nem refuta."
    if group == hypothesis:
        return "a evidência do modelo é compatível com a hipótese."
    return (
        f"a evidência do modelo aponta {GROUP_LABELS[group]}, contrariando a hipótese; "
        "divergência registrada."
    )


def render_comparison_report(
    documents: list[dict],
    lookup: CatalogLookup,
    catalog_parties: list[str],
    model_version: str,
    hypotheses: dict[str, str] | None = None,
    sensitivity: list[dict] | None = None,
) -> str:
    hypotheses = DEFAULT_HYPOTHESES if hypotheses is None else hypotheses
    comparisons = [compare_document(document, lookup) for document in documents]
    counts = {
        outcome: sum(1 for c in comparisons if c.outcome == outcome) for outcome in OUTCOME_LABELS
    }
    modeled = {
        c.document["political_party_id"] for c in comparisons if c.outcome != "not_comparable"
    }
    lines = [
        "# Modelo de classificação partidária x catálogo atual",
        "",
        f"Gerado de forma determinística pelo `{model_version}`; "
        "o catálogo de produção não foi alterado.",
        "",
        "Resumo: "
        + "; ".join(f"{label} {counts[key]}" for key, label in OUTCOME_LABELS.items())
        + ".",
        "",
        "## Destaques (hipóteses registradas, nunca usadas no cálculo)",
        "",
    ]
    for party in dict.fromkeys([*HIGHLIGHTED_PARTIES, *hypotheses]):
        lines += _highlight(party, comparisons, hypotheses)
    lines += extreme_label_section(documents)
    lines += changed_category_section([(c.document, c.outcome) for c in comparisons])
    lines += partial_evidence_section(documents)
    if sensitivity:
        lines += sensitivity_section(sensitivity)
    lines += [
        "## Todos os partidos e períodos",
        "",
        "| Partido | Período | Modelo | Escore | Confiança | Catálogo | Resultado |",
        "|---|---|---|---|---|---|---|",
    ]
    shown = [c for c in comparisons if c.outcome != "not_comparable" or c.document["evidence_used"]]
    lines += [_row(c) for c in shown]
    lines += [
        "",
        f"{len(comparisons) - len(shown)} combinações sem evidência e sem catálogo omitidas.",
    ]
    pending = sorted(p for p in catalog_parties if normalize_party_key(p) not in modeled)
    lines += [
        "",
        "## Partidos do catálogo sem classificação comparável do modelo",
        "",
        ", ".join(pending) or "nenhum",
        "",
    ]
    return "\n".join(lines)
