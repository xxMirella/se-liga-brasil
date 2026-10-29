"""The comparison page shows survey and behavior-based classifications without database access."""

import copy

import pytest

from application.public_cache import public_cache_policy
from application.public_portal import dispatch_portal_request
from service.party_orientation_comparison.detail import render_model_cell
from service.party_orientation_comparison.page import render_party_comparison_page
from service.party_orientation_comparison.rows import (
    build_rows,
    compare_groups,
    model_score_on_survey_scale,
    outcome_counts,
)
from service.party_orientation_comparison.snapshot import load_snapshot, validate_snapshot
from service.party_orientation_comparison.snapshot_builder import build_snapshot

PERIODS = [
    {"period_id": "2015-2018", "year_start": 2015, "year_end": 2018},
    {"period_id": "2019-2022", "year_start": 2019, "year_end": 2022},
]


def dimension(evidence_count=0, score=None):
    return {
        "status": "sufficient" if score is not None else "insufficient_evidence",
        "score": score,
        "indicative_score_not_for_use": score,
        "evidence_count": evidence_count,
        "indicator_count": 1 if evidence_count else 0,
        "layers": [{"layer": "votes", "evidence_count": evidence_count}] if evidence_count else [],
    }


def model_document(period, category="insufficient_evidence", score=None, evidence=0):
    return {
        "political_party": "PDT",
        "period": period,
        "category": category,
        "category_label": category,
        "overall_score": score,
        "confidence_label": "low",
        "overall_insufficiency_reasons": ["no_scoring_evidence"],
        "dimensions": {
            "economic": dimension(evidence, score),
            "sociocultural": dimension(evidence, score),
        },
        "explanation_summary": ["Tema (economic): puxa para esquerda (-0.500)."],
        "documented_extreme_markers": [],
        "model_version": "model.test",
        "rubric_version": "rubric.test",
    }


def survey_observation(score, year=2018, political_party="PDT"):
    return {
        "political_party": political_party,
        "reference_year": year,
        "score": score,
        "respondents": 400,
    }


@pytest.fixture
def snapshot():
    documents = [
        model_document(PERIODS[0], "left", -0.5, evidence=4),
        model_document(PERIODS[1]),
    ]
    return build_snapshot(
        [survey_observation(3.0), survey_observation(7.0, 2022)],
        documents,
        catalog_version="catalog.test",
        generated_on="2026-10-29",
    )


def test_builder_keeps_both_methods_and_marks_proposal_status(snapshot):
    assert snapshot["status"] == "proposta_em_revisao"
    assert snapshot["model_version"] == "model.test"
    rows = build_rows(snapshot, "pdt")
    assert [(row.period_id, row.outcome) for row in rows] == [
        ("2015-2018", "agree"),
        ("2019-2022", "not_comparable"),
    ]
    assert rows[0].survey[0]["group"] == "left"


def test_insufficient_evidence_is_never_filled(snapshot):
    row = build_rows(snapshot, "PDT")[1]
    assert row.survey[0]["group"] == "right"
    assert "não tem evidência suficiente" in row.reason
    assert "nenhuma evidência no período" in render_model_cell(row.model)
    partial = {**row.model, "no_evidence": False}
    assert "sem nota: evidência insuficiente" in render_model_cell(partial)


@pytest.mark.parametrize(
    ("survey_groups", "model_group", "expected"),
    [
        (["left"], "left", "agree"),
        (["left"], "right", "disagree"),
        (["left", "right"], "left", "mixed"),
        ([], "left", "not_comparable"),
        (["left"], "undetermined", "not_comparable"),
        (["left"], "mixed", "not_comparable"),
    ],
)
def test_outcome_rules(survey_groups, model_group, expected):
    survey = [{"group": group} for group in survey_groups]
    assert compare_groups(survey, {"group": model_group})[0] == expected


def test_scale_conversion_matches_catalog_adapter():
    assert model_score_on_survey_scale(-1) == 0
    assert model_score_on_survey_scale(0) == 5
    assert model_score_on_survey_scale(0.5) == 7.5
    assert model_score_on_survey_scale(None) is None


def test_extreme_label_is_only_a_proposal(snapshot):
    model = copy.deepcopy(snapshot["political_parties"][0]["rows"][0]["model"])
    model["category"] = "extreme_left"
    assert "aguarda revisão humana" in render_model_cell(model)


def test_survey_only_party_and_mixed_versions():
    documents = [model_document(PERIODS[0])]
    built = build_snapshot(
        [survey_observation(5.0, political_party="PTC")],
        documents,
        catalog_version="catalog.test",
        generated_on="2026-10-29",
    )
    entry = next(e for e in built["political_parties"] if e["political_party"] == "PTC")
    assert entry["rows"][0]["model"] is None
    mixed = [documents[0], {**model_document(PERIODS[1]), "model_version": "other"}]
    with pytest.raises(ValueError, match="MIXED_MODEL_VERSION"):
        build_snapshot([], mixed, catalog_version="c", generated_on="2026-10-29")


def test_validation_rejects_unknown_schema_and_periods(snapshot):
    with pytest.raises(ValueError, match="SCHEMA_NOT_SUPPORTED"):
        validate_snapshot({**snapshot, "schema_version": "old"})
    broken = copy.deepcopy(snapshot)
    broken["political_parties"][0]["rows"][0]["period_id"] = "1900-1903"
    with pytest.raises(ValueError, match="PERIOD_UNKNOWN"):
        validate_snapshot(broken)


def test_bundled_snapshot_is_valid_and_consistent():
    bundled = load_snapshot()
    assert bundled["status"] == "proposta_em_revisao"
    names = [entry["political_party"] for entry in bundled["political_parties"]]
    assert len(names) == len(set(names)) and "PDT" in names and "PCdoB" in names
    total = outcome_counts([r for n in names for r in build_rows(bundled, n)])
    assert sum(total.values()) == sum(len(e["rows"]) for e in bundled["political_parties"])


ROUTE = "/comparacao-de-classificacoes"


@pytest.mark.parametrize("path", [ROUTE, ROUTE + "/"])
def test_route_serves_overview_without_database(path):
    response = dispatch_portal_request(object(), path)
    assert response.status == 200
    body = response.body.decode()
    assert "percepção de especialistas" in body
    assert "evidência insuficiente" in body
    assert 'href="/comparacao-de-classificacoes?partido=PDT"' in body
    assert "/assets/party-comparison.css" in body


def test_party_filter_shows_one_party_table():
    response = dispatch_portal_request(object(), "/comparacao-de-classificacoes?partido=pdt")
    body = response.body.decode()
    assert response.status == 200
    assert "PDT: pesquisa de especialistas e modelo de atuação" in body
    assert 'scope="row">2015–2018' in body
    assert "PCdoB: pesquisa" not in body


@pytest.mark.parametrize("query", ["?partido=XYZ", "?outro=1", "?partido=PT&partido=PL"])
def test_invalid_filters_return_html_400(query):
    response = dispatch_portal_request(object(), "/comparacao-de-classificacoes" + query)
    assert response.status == 400
    assert response.content_type.startswith("text/html")


def test_stylesheet_navigation_and_cache():
    css = dispatch_portal_request(object(), "/assets/party-comparison.css")
    assert css.status == 200 and ".comparison-table" in css.body.decode()
    assert 'aria-current="page"' in render_party_comparison_page()
    assert "s-maxage=3600" in public_cache_policy("/comparacao-de-classificacoes", 200)
    assert public_cache_policy("/comparacao-de-classificacoes", 400) == "no-store"
    assert public_cache_policy("/assets/party-comparison.css", 200).startswith("public")
