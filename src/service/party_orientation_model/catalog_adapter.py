"""Convert model output to the catalog format. NOT wired to the dashboard (needs approval)."""

from service.party_orientation_model.contracts import (
    CATEGORY_CENTER,
    CATEGORY_CENTER_LEFT,
    CATEGORY_CENTER_RIGHT,
    CATEGORY_CONTROVERSIAL,
    CATEGORY_EXTREME_LEFT,
    CATEGORY_EXTREME_RIGHT,
    CATEGORY_INSUFFICIENT,
    CATEGORY_LEFT,
    CATEGORY_MIXED_PROFILE,
    CATEGORY_RADICAL_LEFT,
    CATEGORY_RADICAL_RIGHT,
    CATEGORY_RIGHT,
)

CATALOG_METHODOLOGY_ID = "party_behavior_model_v1"
CATALOG_STATUS = "model_classification"
# The catalog knows only left/center/right: a center-* category keeps its side, not its nuance.
CATALOG_GROUP_BY_CATEGORY = {
    CATEGORY_EXTREME_LEFT: "left",
    CATEGORY_RADICAL_LEFT: "left",
    CATEGORY_LEFT: "left",
    CATEGORY_CENTER_LEFT: "left",
    CATEGORY_CENTER: "center",
    CATEGORY_CENTER_RIGHT: "right",
    CATEGORY_RIGHT: "right",
    CATEGORY_RADICAL_RIGHT: "right",
    CATEGORY_EXTREME_RIGHT: "right",
    CATEGORY_MIXED_PROFILE: "mixed",
    CATEGORY_CONTROVERSIAL: "controversial",
    CATEGORY_INSUFFICIENT: "undetermined",
}


def catalog_group(model_category: str) -> str:
    return CATALOG_GROUP_BY_CATEGORY[model_category]


def to_catalog_observation(document: dict) -> dict | None:
    """Catalog-shaped row (0-10 scale) or None when the model made no classification."""
    group = catalog_group(document["category"])
    if document["overall_score"] is None or group in ("undetermined", "controversial", "mixed"):
        return None
    period = document["period"]
    return {
        "political_party": document["political_party"],
        "year_start": period["year_start"],
        "year_end": period["year_end"],
        "reference_year": period["year_end"],
        "methodology_id": CATALOG_METHODOLOGY_ID,
        "score": 5 + 5 * document["overall_score"],
        "respondents": None,
        "respondent_standard_deviation": None,
        "source_column": document["input_digest_sha256"],
        "source_url": f"model:{document['model_version']}/{document['rubric_version']}",
        "status": CATALOG_STATUS,
        "model_category": document["category"],
        "catalog_group": group,
        "confidence_label": document["confidence_label"],
    }


def to_catalog_observations(documents: list[dict]) -> list[dict]:
    rows = (to_catalog_observation(document) for document in documents)
    return [row for row in rows if row is not None]
