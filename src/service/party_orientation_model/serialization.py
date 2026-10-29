"""Auditable JSON document for one party and period; deterministic (rounded, sorted, no clock)."""

from service.party_orientation_model.assessment import DimensionAssessment
from service.party_orientation_model.classifier import PartyPeriodClassification
from service.party_orientation_model.contracts import CATEGORY_LABELS, ScoredEvidence

DOCUMENT_SCHEMA = "party_orientation_classification.v1"
DECIMALS = 6


def rounded(value):
    if isinstance(value, float):
        return round(value, DECIMALS)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [rounded(item) for item in value]
    return value


def _evidence_entry(scored: ScoredEvidence, contribution: float | None) -> dict:
    item = scored.item
    return {
        "evidence_id": item.evidence_id,
        "layer": item.layer,
        "dimension": item.dimension,
        "indicator_id": item.indicator_id,
        "policy_reference_id": item.policy_reference_id,
        "stance": item.stance,
        "oriented_stance": scored.oriented_stance,
        "weight": scored.weight,
        "contribution": contribution,
        "proof_level": item.proof_level,
        "attribution_basis": item.attribution_basis,
        "temporal_factor": scored.temporal_factor,
        "carried_from_political_party": scored.carried_from,
        "validity_years": [item.year_start, item.year_end],
        "source_id": item.source_id,
        "source_url": item.source_url,
        "source_date": item.source_date.isoformat(),
        "extreme_markers": list(item.extreme_markers),
    }


def _dimension_entry(assessment: DimensionAssessment) -> dict:
    score = assessment.score
    interval = score.interval if score else (None, None)
    sufficient = assessment.is_sufficient
    return {
        "status": assessment.status,
        "score": score.score if score and sufficient else None,
        "indicative_score_not_for_use": None if sufficient or not score else score.score,
        "interval_95": list(interval) if sufficient else None,
        "standard_error": score.standard_error if score else None,
        "confidence": assessment.confidence,
        "confidence_terms": assessment.confidence_terms,
        "evidence_count": assessment.item_count,
        "behavior_evidence_count": assessment.behavior_item_count,
        "indicator_count": assessment.indicator_count,
        "source_count": assessment.source_count,
        "layers_agree": assessment.layers_agree,
        "insufficiency_reasons": list(assessment.insufficiency_reasons),
        "layers": [
            {
                "layer": layer.layer,
                "mean": layer.mean,
                "effective_share": layer.effective_share,
                "evidence_count": layer.item_count,
                "effective_sample_size": layer.effective_sample_size,
                "standard_error": layer.standard_error,
            }
            for layer in (score.layer_scores if score else ())
        ],
    }


def _contributions(classification: PartyPeriodClassification) -> dict[str, float]:
    merged = {}
    for assessment in classification.assessments.values():
        if assessment.score is not None:
            merged |= assessment.score.contributions
    return merged


def classification_document(
    classification: PartyPeriodClassification, model_digest: str = ""
) -> dict:
    contributions = _contributions(classification)
    overall = classification.overall
    decision = classification.decision
    document = {
        "schema_version": DOCUMENT_SCHEMA,
        "model_version": classification.model_version,
        "rubric_version": classification.rubric_version,
        "political_party": classification.political_party,
        "political_party_id": classification.political_party_id,
        "period": {
            "period_id": classification.period.period_id,
            "year_start": classification.period.year_start,
            "year_end": classification.period.year_end,
        },
        "category": classification.category,
        "category_label": CATEGORY_LABELS[classification.category],
        "base_band_category": decision.base_category if decision else None,
        "decision_notes": list(decision.notes) if decision else [],
        "documented_extreme_markers": list(decision.documented_extreme_markers) if decision else [],
        "overall_score": overall.score if overall else None,
        "overall_interval_95": list(overall.interval) if overall else None,
        "overall_confidence": overall.confidence if overall else None,
        "confidence_label": classification.confidence_label,
        "overall_insufficiency_reasons": list(classification.overall_reasons),
        "dimensions": {
            name: _dimension_entry(a) for name, a in sorted(classification.assessments.items())
        },
        "evidence_used": [
            _evidence_entry(s, contributions.get(s.item.evidence_id))
            for s in classification.used_evidence
        ],
        "evidence_excluded": [
            {"evidence_id": e.evidence_id, "reason": e.reason}
            for e in classification.excluded_evidence
        ],
        "explanation_by_indicator": list(classification.explanations),
        "explanation_summary": list(classification.summary),
        "divergences": list(classification.divergences),
        "expert_calibration": classification.calibration,
        "limitations": list(classification.limitations),
        "input_digest_sha256": classification.input_digest,
    }
    return rounded(document)
