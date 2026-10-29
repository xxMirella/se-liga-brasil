"""Orchestrate one party and one period: select evidence, score, assess, categorize, audit."""

import hashlib
import json
from dataclasses import asdict, dataclass

from service.party_orientation_model.applicability import (
    index_evidence_by_party,
    select_applicable_evidence,
)
from service.party_orientation_model.assessment import (
    DimensionAssessment,
    assess_dimension,
    confidence_label,
    counted_items,
)
from service.party_orientation_model.categories import CategoryDecision, decide_category
from service.party_orientation_model.contracts import (
    CATEGORY_INSUFFICIENT,
    MODEL_VERSION,
    SCORING_DIMENSIONS,
    EvidenceItem,
    ExcludedEvidence,
    PartySuccession,
    Period,
    Rubric,
    ScoredEvidence,
    normalize_party_key,
)
from service.party_orientation_model.divergence import (
    behavior_dimension_scores,
    dimension_divergences,
    expert_calibration,
    indicator_divergences,
    self_declaration_divergence,
)
from service.party_orientation_model.explanation import explain_dimension, summarize
from service.party_orientation_model.overall import (
    OverallScore,
    combine_behavior_scores,
    combine_dimensions,
)

STANDING_LIMITATIONS = (
    "Escala de -1 (esquerda) a +1 (direita) é posição relativa nos indicadores da rubrica, "
    "não julgamento de mérito.",
    "Vale somente para o período indicado; nada é herdado do presente ou do passado.",
    "Pesquisas de especialistas servem de calibração e não entram na pontuação.",
    "Ausência de evidência não é evidência de posição: faltas reduzem a confiança.",
    "Pesos e cortes são decisões editoriais da rubrica, não parâmetros validados empiricamente.",
    "Intervalos e confiança são heurísticas condicionais; não são cobertura frequentista "
    "nem probabilidade de a ideologia estar correta. Evidências podem ser dependentes.",
)


@dataclass(frozen=True)
class PartyPeriodClassification:
    political_party: str
    political_party_id: str
    period: Period
    category: str
    decision: CategoryDecision | None
    overall: OverallScore | None
    overall_reasons: tuple[str, ...]
    confidence_label: str
    assessments: dict[str, DimensionAssessment]
    used_evidence: tuple[ScoredEvidence, ...]
    excluded_evidence: tuple[ExcludedEvidence, ...]
    explanations: tuple[dict, ...]
    summary: tuple[str, ...]
    divergences: tuple[dict, ...]
    calibration: dict | None
    limitations: tuple[str, ...]
    input_digest: str
    model_version: str = MODEL_VERSION
    rubric_version: str = ""


def input_digest(
    political_party: str, period: Period, used: list[ScoredEvidence], rubric: Rubric
) -> str:
    payload = {
        "party": normalize_party_key(political_party),
        "period": asdict(period),
        "rubric": asdict(rubric),
        "model_version": MODEL_VERSION,
        "evidence": [asdict(s) for s in sorted(used, key=lambda s: s.item.evidence_id)],
    }
    canonical = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_limitations(
    assessments: dict[str, DimensionAssessment],
    overall_reasons: tuple[str, ...],
    decision: CategoryDecision | None,
    used: list[ScoredEvidence],
) -> tuple[str, ...]:
    lines = list(STANDING_LIMITATIONS)
    for name, assessment in sorted(assessments.items()):
        for reason in assessment.insufficiency_reasons:
            lines.append(f"Dimensão {name}: {reason}.")
    lines.extend(f"Classificação final: {reason}." for reason in overall_reasons)
    if decision is not None:
        lines.extend(decision.notes)
    if any(s.carried_from for s in used):
        lines.append(
            "Há evidência herdada de sigla anterior por sucessão com fonte; peso reduzido."
        )
    return tuple(lines)


def _decide(
    overall: OverallScore | None,
    assessments: dict[str, DimensionAssessment],
    counted: list[ScoredEvidence],
    rubric: Rubric,
) -> tuple[str, CategoryDecision | None]:
    if overall is None:
        return CATEGORY_INSUFFICIENT, None
    dimension_scores = {n: a.score.score for n, a in assessments.items() if a.is_sufficient}
    decision = decide_category(overall.score, overall.interval, dimension_scores, counted, rubric)
    return decision.category, decision


def classify_party_period(
    political_party: str,
    period: Period,
    evidence: tuple[EvidenceItem, ...],
    successions: tuple[PartySuccession, ...],
    rubric: Rubric,
    *,
    evidence_index: dict[str, list[EvidenceItem]] | None = None,
) -> PartyPeriodClassification:
    indexed = index_evidence_by_party(evidence) if evidence_index is None else evidence_index
    used, excluded = select_applicable_evidence(
        political_party, period, indexed, successions, rubric
    )
    by_dimension = {d: [s for s in used if s.item.dimension == d] for d in SCORING_DIMENSIONS}
    assessments = {d: assess_dimension(d, by_dimension[d], rubric) for d in SCORING_DIMENSIONS}
    overall, reasons = combine_dimensions(assessments, rubric)
    counted = [s for d in SCORING_DIMENSIONS for s in counted_items(by_dimension[d], rubric)]
    category, decision = _decide(overall, assessments, counted, rubric)
    explanations = [
        entry
        for d in SCORING_DIMENSIONS
        for entry in explain_dimension(
            assessments[d], counted_items(by_dimension[d], rubric), rubric
        )
    ]
    return PartyPeriodClassification(
        political_party=political_party,
        political_party_id=normalize_party_key(political_party),
        period=period,
        category=category,
        decision=decision,
        overall=overall,
        overall_reasons=reasons,
        confidence_label=confidence_label(overall.confidence, rubric) if overall else "low",
        assessments=assessments,
        used_evidence=tuple(sorted(used, key=lambda s: s.item.evidence_id)),
        excluded_evidence=tuple(sorted(excluded, key=lambda e: e.evidence_id)),
        explanations=tuple(explanations),
        summary=tuple(summarize(sorted(explanations, key=lambda e: -abs(e["net_contribution"])))),
        divergences=tuple(_divergences(used, rubric)),
        calibration=expert_calibration(used, overall.score if overall else None, rubric),
        limitations=build_limitations(assessments, reasons, decision, used),
        input_digest=input_digest(political_party, period, used, rubric),
        rubric_version=rubric.rubric_version,
    )


def _divergences(used: list[ScoredEvidence], rubric: Rubric) -> list[dict]:
    behavior_overall = combine_behavior_scores(behavior_dimension_scores(used, rubric), rubric)
    return [
        *dimension_divergences(used, rubric),
        *indicator_divergences(used, rubric),
        *self_declaration_divergence(used, behavior_overall, rubric),
    ]
