"""Scoring, weights, behavior over discourse, sufficiency, confidence and determinism."""

import random

import pytest
from party_orientation_fixtures import (
    PERIOD_2019_2022,
    balanced_party_evidence,
    evidence,
    make_rubric,
)

from service.party_orientation_model.classifier import classify_party_period
from service.party_orientation_model.contracts import CATEGORY_INSUFFICIENT
from service.party_orientation_model.serialization import classification_document

RUBRIC = make_rubric()
ECO = "economic_privatization"
SOC = "sociocultural_traditional_values"


def classify(items, party="ALFA", successions=()):
    return classify_party_period(party, PERIOD_2019_2022, tuple(items), tuple(successions), RUBRIC)


def dimension_items(party, economic_stance, social_stance, extra=()):
    items = [
        evidence(RUBRIC, "v-eco", party, "votes", ECO, economic_stance),
        evidence(RUBRIC, "i-eco", party, "implemented_policies", ECO, economic_stance),
        evidence(RUBRIC, "v-soc", party, "votes", SOC, social_stance),
        evidence(RUBRIC, "i-soc", party, "implemented_policies", SOC, social_stance),
    ]
    return [*items, *extra]


def test_layers_are_combined_with_rubric_weights_and_discourse_cap():
    items = [
        evidence(RUBRIC, "v1", "ALFA", "votes", ECO, 1.0),
        evidence(RUBRIC, "d1", "ALFA", "discourse", ECO, -1.0),
        evidence(RUBRIC, "v2", "ALFA", "votes", SOC, 1.0),
        evidence(RUBRIC, "d2", "ALFA", "discourse", SOC, -1.0),
    ]
    result = classify(items)
    layers = {layer.layer: layer for layer in result.assessments["economic"].score.layer_scores}
    # votes 0.30 vs discourse min(0.20, 0.4 * 0.30 = 0.12): shares 0.714 and 0.286.
    assert layers["votes"].effective_share == pytest.approx(0.30 / 0.42)
    assert layers["discourse"].effective_share == pytest.approx(0.12 / 0.42)
    assert result.assessments["economic"].score.score == pytest.approx((0.30 - 0.12) / 0.42)


def test_indicator_direction_orients_the_stance():
    # supporting social spending (direction -1) is a left position
    item = evidence(RUBRIC, "x", "ALFA", "votes", "economic_social_spending", 1.0)
    result = classify([item])
    assert result.used_evidence[0].oriented_stance == -1.0


def test_proof_level_scales_evidence_weight():
    strong = evidence(RUBRIC, "a", "ALFA", "votes", ECO, 1.0, proof="documented_primary")
    weak = evidence(RUBRIC, "b", "ALFA", "votes", ECO, 1.0, proof="reported")
    weights = {s.item.evidence_id: s.weight for s in classify([strong, weak]).used_evidence}
    assert weights["a"] == pytest.approx(1.0)
    assert weights["b"] == pytest.approx(0.4)


def test_weighted_mean_inside_a_layer_uses_indicator_and_proof_weights():
    heavy = evidence(RUBRIC, "h", "ALFA", "votes", ECO, 1.0)  # weight 1.0
    light = evidence(RUBRIC, "l", "ALFA", "votes", ECO, -1.0, proof="reported")  # weight 0.4
    result = classify([heavy, light])
    layer = result.assessments["economic"].score.layer_scores[0]
    assert layer.mean == pytest.approx((1.0 - 0.4) / 1.4)


@pytest.mark.parametrize("discourse_stance", [-1.0, 1.0])
def test_behavior_outweighs_discourse_whatever_the_discourse_says(discourse_stance):
    items = dimension_items(
        "ALFA",
        0.8,
        0.8,
        [
            evidence(RUBRIC, "d-eco", "ALFA", "discourse", ECO, discourse_stance),
            evidence(RUBRIC, "d-soc", "ALFA", "discourse", SOC, discourse_stance),
        ],
    )
    for assessment in classify(items).assessments.values():
        shares = {layer.layer: layer.effective_share for layer in assessment.score.layer_scores}
        behavior = sum(v for layer, v in shares.items() if layer != "discourse")
        assert behavior > shares["discourse"]
        assert assessment.score.score > 0  # follows the behavior, not the discourse sign


def test_discourse_share_stays_below_behavior_even_with_one_thin_behavior_layer():
    items = [
        evidence(RUBRIC, "f", "ALFA", "thematic_focus", ECO, 0.5),  # weight 0.05 only
        evidence(RUBRIC, "d", "ALFA", "discourse", ECO, -1.0),
    ]
    score = classify(items).assessments["economic"].score
    shares = {layer.layer: layer.effective_share for layer in score.layer_scores}
    assert shares["discourse"] < shares["thematic_focus"]


def test_discourse_alone_is_insufficient_never_a_guess():
    items = [evidence(RUBRIC, f"d{i}", "ALFA", "discourse", ECO, 1.0) for i in range(6)]
    items += [evidence(RUBRIC, f"s{i}", "ALFA", "discourse", SOC, 1.0) for i in range(6)]
    result = classify(items)
    assert result.category == CATEGORY_INSUFFICIENT
    assert "too_few_behavior_items" in result.assessments["economic"].insufficiency_reasons


def test_no_evidence_gives_insufficient_without_score():
    result = classify([])
    document = classification_document(result)
    assert document["category"] == CATEGORY_INSUFFICIENT
    assert document["overall_score"] is None
    assert document["dimensions"]["economic"]["insufficiency_reasons"] == ["no_scoring_evidence"]


def test_thin_evidence_hides_the_score_but_audits_the_indicative_value():
    document = classification_document(classify([evidence(RUBRIC, "a", "ALFA", "votes", ECO, 1.0)]))
    economic = document["dimensions"]["economic"]
    assert economic["score"] is None
    assert economic["indicative_score_not_for_use"] == pytest.approx(1.0)
    assert document["category"] == CATEGORY_INSUFFICIENT


def test_one_sufficient_dimension_is_not_enough_when_both_are_required():
    items = [evidence(RUBRIC, f"e{i}", "ALFA", "votes", ECO, 0.9) for i in range(6)]
    items += [
        evidence(RUBRIC, f"f{i}", "ALFA", "bills", "economic_labor_regulation", -0.9)
        for i in range(2)
    ]
    result = classify(items)
    assert result.assessments["economic"].is_sufficient
    assert result.category == CATEGORY_INSUFFICIENT
    assert any("required_dimension_insufficient:sociocultural" in r for r in result.overall_reasons)


def test_minimum_confidence_rule_blocks_a_sufficient_count_with_chaotic_evidence():
    from party_orientation_fixtures import rubric_document

    from service.party_orientation_model.rubric import parse_rubric

    document = rubric_document()
    document["sufficiency"] = document["sufficiency"] | {"minimum_confidence": 0.99}
    strict = parse_rubric(document)
    items = balanced_party_evidence(strict, "ALFA", 0.5)
    result = classify_party_period("ALFA", PERIOD_2019_2022, items, (), strict)
    assert "confidence_below_minimum" in result.assessments["economic"].insufficiency_reasons
    assert result.category == CATEGORY_INSUFFICIENT


def test_more_agreeing_evidence_raises_confidence_and_narrows_interval():
    few = classify(dimension_items("ALFA", 0.7, 0.7))
    many = classify(balanced_party_evidence(RUBRIC, "ALFA", 0.7))
    few_economic, many_economic = few.assessments["economic"], many.assessments["economic"]
    assert many_economic.confidence > few_economic.confidence
    low_few, high_few = few_economic.score.interval
    low_many, high_many = many_economic.score.interval
    assert high_many - low_many < high_few - low_few


def test_conflicting_evidence_lowers_agreement_and_confidence():
    aligned = classify(balanced_party_evidence(RUBRIC, "ALFA", 0.6))
    mixed_items = []
    for index, item in enumerate(balanced_party_evidence(RUBRIC, "ALFA", 0.6)):
        sign = 1 if (index // 2) % 2 == 0 else -1
        mixed_items.append(
            evidence(
                RUBRIC,
                item.evidence_id,
                "ALFA",
                item.layer,
                item.indicator_id,
                0.9 * sign * RUBRIC.indicators[item.indicator_id].direction,
            )
        )
    mixed = classify(mixed_items)
    assert (
        mixed.assessments["economic"].confidence_terms["agreement"]
        < aligned.assessments["economic"].confidence_terms["agreement"]
    )


def test_contributions_sum_to_the_dimension_score():
    result = classify(balanced_party_evidence(RUBRIC, "ALFA", 0.4))
    for assessment in result.assessments.values():
        total = sum(assessment.score.contributions.values())
        assert total == pytest.approx(assessment.score.score)


def test_explanation_lists_indicator_pull_and_evidence():
    items = dimension_items("ALFA", 0.9, -0.9)
    document = classification_document(classify(items))
    by_indicator = {e["indicator_id"]: e for e in document["explanation_by_indicator"]}
    assert by_indicator[ECO]["pulls"] == "right"
    assert by_indicator[SOC]["pulls"] == "left"
    assert {e["evidence_id"] for e in by_indicator[ECO]["evidence"]} == {"v-eco", "i-eco"}
    assert document["explanation_summary"]


def test_expert_survey_is_calibration_only_and_never_changes_the_score():
    base = list(balanced_party_evidence(RUBRIC, "ALFA", 0.5))
    expert = evidence(RUBRIC, "x1", "ALFA", "expert_survey", "expert_position", -0.9)
    without = classification_document(classify(base))
    with_expert = classification_document(classify([*base, expert]))
    assert with_expert["overall_score"] == without["overall_score"]
    calibration = with_expert["expert_calibration"]
    assert calibration["expert_reference_score"] == pytest.approx(-0.9)
    assert calibration["exceeds_threshold"] is True
    assert without["expert_calibration"] is None


def test_deterministic_regardless_of_input_order_and_repetition():
    items = list(balanced_party_evidence(RUBRIC, "ALFA", 0.45))
    first = classification_document(classify(items))
    shuffled = items[:]
    random.Random(7).shuffle(shuffled)
    assert classification_document(classify(shuffled)) == first
    assert classification_document(classify(items)) == first
    assert len(first["input_digest_sha256"]) == 64


def test_digest_changes_when_evidence_changes():
    items = list(balanced_party_evidence(RUBRIC, "ALFA", 0.45))
    changed = [*items[:-1], evidence(RUBRIC, "e-soc-d", "ALFA", "discourse", SOC, -0.45)]
    assert (
        classification_document(classify(items))["input_digest_sha256"]
        != classification_document(classify(changed))["input_digest_sha256"]
    )
