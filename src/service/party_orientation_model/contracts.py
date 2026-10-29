"""Immutable contracts of the party orientation model; no network, database or file access."""

from dataclasses import dataclass, field
from datetime import date
from math import isfinite

MODEL_VERSION = "party_orientation_model.v1"
EVIDENCE_SCHEMA = "party_orientation_evidence.v1"
RUBRIC_SCHEMA = "party_orientation_rubric.v1"
SUCCESSION_SCHEMA = "political_party_succession.v1"

LAYER_VOTES = "votes"
LAYER_IMPLEMENTED = "implemented_policies"
LAYER_SUPPORTED = "supported_policies"
LAYER_BILLS = "bills"
LAYER_FOCUS = "thematic_focus"
LAYER_DISCOURSE = "discourse"
LAYER_EXPERT = "expert_survey"
BEHAVIOR_LAYERS = (LAYER_VOTES, LAYER_IMPLEMENTED, LAYER_SUPPORTED, LAYER_BILLS, LAYER_FOCUS)
SCORING_LAYERS = (*BEHAVIOR_LAYERS, LAYER_DISCOURSE)
ALL_LAYERS = (*SCORING_LAYERS, LAYER_EXPERT)

DIMENSION_ECONOMIC = "economic"
DIMENSION_SOCIOCULTURAL = "sociocultural"
DIMENSION_OVERALL = "overall"
SCORING_DIMENSIONS = (DIMENSION_ECONOMIC, DIMENSION_SOCIOCULTURAL)

# Ordered from weakest to strongest proof.
PROOF_LEVELS = ("reported", "documented_secondary", "documented_primary")

ATTRIBUTION_BASES = (
    "party_leadership_orientation",
    "member_votes_by_affiliation_at_vote_date",
    "party_in_government",
    "party_sponsored_bill",
    "party_official_document",
    "survey_of_experts",
)

CATEGORY_EXTREME_LEFT = "extreme_left"
CATEGORY_RADICAL_LEFT = "radical_left"
CATEGORY_RADICAL_RIGHT = "radical_right"
CATEGORY_MIXED_PROFILE = "mixed_profile"
CATEGORY_LEFT = "left"
CATEGORY_CENTER_LEFT = "center_left"
CATEGORY_CENTER = "center"
CATEGORY_CENTER_RIGHT = "center_right"
CATEGORY_RIGHT = "right"
CATEGORY_EXTREME_RIGHT = "extreme_right"
CATEGORY_INSUFFICIENT = "insufficient_evidence"
CATEGORY_CONTROVERSIAL = "controversial"
ORDERED_BAND_CATEGORIES = (
    CATEGORY_RADICAL_LEFT,
    CATEGORY_LEFT,
    CATEGORY_CENTER_LEFT,
    CATEGORY_CENTER,
    CATEGORY_CENTER_RIGHT,
    CATEGORY_RIGHT,
    CATEGORY_RADICAL_RIGHT,
)
CATEGORY_LABELS = {
    CATEGORY_EXTREME_LEFT: "Extrema esquerda",
    CATEGORY_RADICAL_LEFT: "Esquerda radical (intensidade sem gate extremista)",
    CATEGORY_RADICAL_RIGHT: "Direita radical (intensidade sem gate extremista)",
    CATEGORY_MIXED_PROFILE: "Perfil misto (dimensões em lados opostos)",
    CATEGORY_LEFT: "Esquerda",
    CATEGORY_CENTER_LEFT: "Centro-esquerda",
    CATEGORY_CENTER: "Centro",
    CATEGORY_CENTER_RIGHT: "Centro-direita",
    CATEGORY_RIGHT: "Direita",
    CATEGORY_EXTREME_RIGHT: "Extrema direita",
    CATEGORY_INSUFFICIENT: "Sem classificação: evidência insuficiente",
    CATEGORY_CONTROVERSIAL: "Classificação controversa",
}


class PartyModelContractError(ValueError):
    """Stable error code plus the offending field; messages never embed evidence text."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def proof_rank(level: str) -> int:
    return PROOF_LEVELS.index(level)


def normalize_party_key(political_party: str) -> str:
    """Stable `political_party_id`: casefolded acronym without punctuation."""
    return "".join(character for character in political_party.casefold() if character.isalnum())


def require_finite(value, code: str, detail: str, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise PartyModelContractError(code, detail)
    if not lower <= value <= upper:
        raise PartyModelContractError(code, detail)
    return float(value)


@dataclass(frozen=True)
class Indicator:
    indicator_id: str
    dimension: str
    direction: int  # +1: supporting the policy is right-wing; -1: left-wing
    weight: float
    label: str


@dataclass(frozen=True)
class ExtremeCriterion:
    category: str
    minimum_abs_score: float
    minimum_markers: int
    minimum_proof_level: str
    minimum_sources: int
    require_human_review: bool
    marker_ids: tuple[str, ...]
    require_behavior_marker: bool


@dataclass(frozen=True)
class Period:
    period_id: str
    year_start: int
    year_end: int


@dataclass(frozen=True)
class Sufficiency:
    minimum_items: int
    minimum_behavior_items: int
    minimum_indicators: dict[str, int]
    minimum_sources: int
    minimum_confidence: float
    required_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class Rubric:
    rubric_version: str
    layer_weights: dict[str, float]
    discourse_cap_ratio: float
    proof_multipliers: dict[str, float]
    succession_multiplier: float
    dimension_weights: dict[str, float]
    indicators: dict[str, Indicator]
    band_limits: tuple[float, ...]
    extreme_criteria: dict[str, ExtremeCriterion]
    sufficiency: Sufficiency
    divergence_dimension_threshold: float
    divergence_indicator_threshold: float
    calibration_gap_threshold: float
    prior_standard_deviation: float
    confidence_weights: dict[str, float]
    confidence_target_items: int
    confidence_precision_scale: float
    confidence_labels: tuple[float, float]
    controversy_span_steps: int
    periods: tuple[Period, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    political_party: str
    layer: str
    dimension: str
    indicator_id: str
    stance: float  # -1 opposes the indicator's policy ... +1 supports it
    source_id: str
    source_url: str
    source_date: date
    year_start: int
    year_end: int
    proof_level: str
    attribution_basis: str
    extreme_markers: tuple[str, ...] = ()
    human_reviewed: bool = False
    policy_reference_id: str | None = None
    description: str = ""


@dataclass(frozen=True)
class PartySuccession:
    predecessor: str
    successor: str
    effective_date: date
    source_url: str
    source_date: date


@dataclass(frozen=True)
class ScoredEvidence:
    item: EvidenceItem
    oriented_stance: float
    weight: float
    temporal_factor: float
    carried_from: str | None = None


@dataclass(frozen=True)
class ExcludedEvidence:
    evidence_id: str
    reason: str
