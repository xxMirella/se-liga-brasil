"""Build the compact survey-versus-model snapshot; pure functions, no file or network access."""

from service.party_orientation_model.catalog_adapter import catalog_group
from service.political_dashboard.political_orientation_catalog import score_category

SCHEMA_VERSION = "party_orientation_comparison_snapshot.v1"
STATUS_UNDER_REVIEW = "proposta_em_revisao"
DIMENSIONS = ("economic", "sociocultural")
MAX_EXPLANATIONS = 3
INSUFFICIENT_CATEGORY = "insufficient_evidence"


def period_id_of(year, periods):
    for period in periods:
        if period["year_start"] <= year <= period["year_end"]:
            return period["period_id"]
    return None


def survey_entries_by_period(observations, periods):
    """Group dated survey estimates by (political_party, period); no interpolation."""
    grouped = {}
    for observation in observations:
        period_id = period_id_of(observation["reference_year"], periods)
        if period_id is None:
            continue
        entry = {
            "year": observation["reference_year"],
            "score": round(observation["score"], 2),
            "respondents": observation["respondents"],
            "group": score_category(observation["score"]),
        }
        grouped.setdefault((observation["political_party"], period_id), []).append(entry)
    return grouped


def dimension_block(dimension):
    return {
        "status": dimension["status"],
        "score": dimension["score"],
        "indicative_score": dimension["indicative_score_not_for_use"],
        "evidence_count": dimension["evidence_count"],
        "indicator_count": dimension["indicator_count"],
        "layers": {layer["layer"]: layer["evidence_count"] for layer in dimension["layers"]},
    }


def model_block(document):
    return {
        "category": document["category"],
        "category_label": document["category_label"],
        "group": catalog_group(document["category"]),
        "overall_score": document["overall_score"],
        "confidence_label": document["confidence_label"],
        "insufficiency_reasons": list(document["overall_insufficiency_reasons"]),
        "dimensions": {name: dimension_block(document["dimensions"][name]) for name in DIMENSIONS},
        "explanations": list(document["explanation_summary"][:MAX_EXPLANATIONS]),
        "extreme_markers": list(document["documented_extreme_markers"]),
    }


def has_model_evidence(block):
    counted = sum(dimension["evidence_count"] for dimension in block["dimensions"].values())
    return counted > 0 or block["category"] != INSUFFICIENT_CATEGORY


def single_version(documents, key):
    versions = {document[key] for document in documents}
    if len(versions) != 1:
        raise ValueError(f"PARTY_ORIENTATION_MODEL_OUTPUT_MIXED_{key.upper()}")
    return versions.pop()


def period_list(documents):
    periods = {document["period"]["period_id"]: document["period"] for document in documents}
    return sorted(periods.values(), key=lambda period: period["year_start"])


def party_rows(political_party, periods, surveys, documents_by_period):
    rows, empty_periods = [], []
    for period in periods:
        survey = surveys.get((political_party, period["period_id"]), [])
        document = documents_by_period.get(period["period_id"])
        model = model_block(document) if document else None
        if model and not has_model_evidence(model):
            model = {**model, "no_evidence": True}
        if not survey and (model is None or model.get("no_evidence")):
            empty_periods.append(period["period_id"])
            continue
        rows.append({"period_id": period["period_id"], "survey": survey, "model": model})
    return {"political_party": political_party, "rows": rows, "empty_periods": empty_periods}


def group_documents_by_party(documents):
    grouped = {}
    for document in documents:
        party_documents = grouped.setdefault(document["political_party"], {})
        party_documents[document["period"]["period_id"]] = document
    return grouped


def merged_party_names(documents_by_party, observations):
    names = {name.casefold(): name for name in documents_by_party}
    for observation in observations:
        names.setdefault(observation["political_party"].casefold(), observation["political_party"])
    return sorted(names.values(), key=str.casefold)


def build_snapshot(observations, documents, *, catalog_version, generated_on):
    if not documents:
        raise ValueError("PARTY_ORIENTATION_MODEL_OUTPUT_EMPTY")
    periods = period_list(documents)
    surveys = survey_entries_by_period(observations, periods)
    documents_by_party = group_documents_by_party(documents)
    casefolded = {name.casefold(): name for name in documents_by_party}
    surveys = {
        (casefolded.get(party.casefold(), party), period_id): entries
        for (party, period_id), entries in surveys.items()
    }
    parties = [
        party_rows(name, periods, surveys, documents_by_party.get(name, {}))
        for name in merged_party_names(documents_by_party, observations)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_UNDER_REVIEW,
        "generated_on": generated_on,
        "catalog_version": catalog_version,
        "model_version": single_version(documents, "model_version"),
        "rubric_version": single_version(documents, "rubric_version"),
        "periods": periods,
        "political_parties": parties,
    }
