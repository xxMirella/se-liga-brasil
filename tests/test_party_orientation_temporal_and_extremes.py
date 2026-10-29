"""Validity windows, sourced successions, category bands, extreme gate, divergences."""

import pytest
from party_orientation_fixtures import (
    PERIOD_2019_2022,
    PERIOD_2023_2026,
    evidence,
    make_rubric,
)

from service.party_orientation_model.categories import band_category, decide_category
from service.party_orientation_model.classifier import classify_party_period
from service.party_orientation_model.contracts import (
    CATEGORY_CENTER,
    CATEGORY_CONTROVERSIAL,
    CATEGORY_EXTREME_RIGHT,
    CATEGORY_INSUFFICIENT,
    CATEGORY_MIXED_PROFILE,
    CATEGORY_RADICAL_RIGHT,
    CATEGORY_RIGHT,
)
from service.party_orientation_model.evidence import parse_successions
from service.party_orientation_model.serialization import classification_document

RUBRIC = make_rubric()
ECO, SOC = "economic_privatization", "sociocultural_traditional_values"
LAYERS = ("votes", "implemented_policies", "bills", "supported_policies")
# (indicator, sign applied to the stance so both indicators of a dimension point the same way)
ECONOMIC_INDICATORS = ((ECO, 1), ("economic_social_spending", -1))
SOCIAL_INDICATORS = ((SOC, 1), ("sociocultural_civil_rights", -1))


def party_items(
    party,
    eco,
    soc,
    *,
    years=(2020, 2020),
    prefix="p",
    markers=(),
    reviewed=False,
    proof="documented_primary",
):
    items = []
    for index, layer in enumerate(LAYERS):
        for tag, indicators, stance in (
            ("eco", ECONOMIC_INDICATORS, eco),
            ("soc", SOCIAL_INDICATORS, soc),
        ):
            indicator, sign = indicators[index % 2]
            items.append(
                evidence(
                    RUBRIC,
                    f"{prefix}-{tag}-{index}",
                    party,
                    layer,
                    indicator,
                    stance * sign,
                    years=years,
                    markers=markers if index == 0 else (),
                    reviewed=reviewed,
                    proof=proof,
                )
            )
    return items


def run(items, party="ALFA", period=PERIOD_2019_2022, successions=()):
    return classify_party_period(party, period, tuple(items), tuple(successions), RUBRIC)


def succession(predecessor, successor, effective="2022-02-01"):
    return parse_successions(
        {
            "schema_version": "political_party_succession.v1",
            "successions": [
                {
                    "predecessor": predecessor,
                    "successor": successor,
                    "effective_date": effective,
                    "source_url": "https://example.invalid/succession",
                    "source_date": effective,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "score,category",
    [
        (-0.9, "radical_left"),
        (-0.6, "left"),
        (-0.3, "center_left"),
        (0.0, "center"),
        (0.3, "center_right"),
        (0.6, "right"),
        (0.95, "radical_right"),
    ],
)
def test_bands(score, category):
    assert band_category(score, RUBRIC.band_limits) == category


def test_evidence_outside_the_period_is_excluded_with_reason():
    items = party_items("ALFA", 0.7, 0.7, years=(2023, 2024))
    result = run(items)
    assert result.category == CATEGORY_INSUFFICIENT
    assert {e.reason for e in result.excluded_evidence} == {"validity_window_outside_period"}


def test_present_is_never_applied_to_the_past():
    items = party_items("ALFA", 0.7, 0.7, years=(2023, 2026))
    assert run(items, period=PERIOD_2023_2026).category == CATEGORY_RIGHT
    assert run(items, period=PERIOD_2019_2022).category == CATEGORY_INSUFFICIENT


def test_same_party_differs_by_period():
    early = party_items("ALFA", -0.7, -0.7, years=(2019, 2022), prefix="a")
    late = party_items("ALFA", 0.7, 0.7, years=(2023, 2026), prefix="b")
    assert run([*early, *late], period=PERIOD_2019_2022).overall.score < 0
    assert run([*early, *late], period=PERIOD_2023_2026).overall.score > 0


def test_long_validity_window_overlapping_part_of_a_period_is_partially_weighted():
    item = evidence(RUBRIC, "long", "ALFA", "discourse", ECO, 0.5, years=(2010, 2020))
    used = run([item]).used_evidence[0]
    assert used.temporal_factor == pytest.approx(2 / 4)


def test_succession_with_source_carries_predecessor_evidence_with_reduced_weight():
    items = party_items("ANTIGO", 0.7, 0.7, years=(2019, 2021))
    direct = run(items, party="ANTIGO")
    inherited = run(items, party="NOVO", successions=succession("ANTIGO", "NOVO"))
    assert inherited.category == direct.category
    assert all(s.carried_from == "ANTIGO" for s in inherited.used_evidence)
    assert inherited.used_evidence[0].weight == pytest.approx(
        direct.used_evidence[0].weight * RUBRIC.succession_multiplier
    )
    assert any("sigla anterior" in text for text in inherited.limitations)


def test_without_a_sourced_succession_nothing_is_inherited():
    items = party_items("ANTIGO", 0.7, 0.7, years=(2019, 2021))
    assert run(items, party="NOVO").category == CATEGORY_INSUFFICIENT


def test_predecessor_evidence_after_effective_date_is_not_carried():
    items = party_items("ANTIGO", 0.7, 0.7, years=(2022, 2022))
    result = run(items, party="NOVO", successions=succession("ANTIGO", "NOVO", "2021-12-01"))
    assert result.category == CATEGORY_INSUFFICIENT
    assert {e.reason for e in result.excluded_evidence} == {
        "dated_after_succession_under_predecessor_name"
    }


def test_successor_evidence_never_flows_back_to_the_predecessor():
    items = party_items("NOVO", 0.7, 0.7, years=(2020, 2021))
    result = run(items, party="ANTIGO", successions=succession("ANTIGO", "NOVO"))
    assert result.category == CATEGORY_INSUFFICIENT


def test_chained_succession_is_transitive():
    chain = (
        *succession("A", "B", "2020-06-01"),
        *succession("B", "C", "2021-06-01"),
    )
    items = party_items("A", 0.7, 0.7, years=(2019, 2019))
    assert run(items, party="C", successions=chain).category == CATEGORY_RIGHT


def test_extreme_needs_a_confirmed_documented_and_reviewed_gate():
    markers = ("marker_right_a", "marker_right_b")
    unreviewed = party_items("ALFA", 1.0, 1.0, markers=markers)
    result = run(unreviewed)
    assert result.category == CATEGORY_RADICAL_RIGHT
    assert any("sem gate confirmado" in note for note in result.decision.notes)
    reviewed = [
        *party_items("ALFA", 1.0, 1.0, markers=markers, reviewed=True, prefix="r"),
    ]
    confirmed = run(reviewed)
    assert confirmed.category == CATEGORY_EXTREME_RIGHT
    assert confirmed.decision.documented_extreme_markers == markers


def test_extreme_requires_independent_sources_and_primary_proof():
    marker_items = [
        evidence(
            RUBRIC,
            f"m{i}",
            "ALFA",
            "votes",
            ECO,
            1.0,
            source="same-source",
            markers=(marker,),
            reviewed=True,
        )
        for i, marker in enumerate(("marker_right_a", "marker_right_b"))
    ]
    assert run([*party_items("ALFA", 1.0, 1.0), *marker_items]).category == CATEGORY_RADICAL_RIGHT
    secondary_only = party_items(
        "ALFA",
        1.0,
        1.0,
        reviewed=True,
        proof="documented_secondary",
        markers=("marker_right_a", "marker_right_b"),
    )
    assert run(secondary_only).category == CATEGORY_RADICAL_RIGHT  # no primary document


def test_high_score_alone_never_yields_extreme_even_with_unreliable_markers():
    items = party_items(
        "ALFA",
        1.0,
        1.0,
        reviewed=True,
        proof="reported",
        markers=("marker_right_a", "marker_right_b"),
    )
    assert run(items).category != CATEGORY_EXTREME_RIGHT


def test_opposite_dimensions_give_mixed_profile_not_a_single_label():
    result = run(party_items("ALFA", -0.7, 0.7))
    assert result.category == CATEGORY_MIXED_PROFILE
    assert classification_document(result)["overall_score"] == pytest.approx(0.0, abs=1e-6)


def test_center_when_both_dimensions_are_near_zero():
    assert run(party_items("ALFA", 0.05, -0.05)).category == CATEGORY_CENTER


def test_controversial_when_interval_spans_many_bands():
    decision = decide_category(0.0, (-0.9, 0.9), {"economic": 0.0}, [], RUBRIC)
    assert decision.category == CATEGORY_CONTROVERSIAL


def test_divergence_between_discourse_and_behavior_is_reported_with_direction():
    items = party_items("ALFA", 0.8, 0.8)
    items += [
        evidence(RUBRIC, "d1", "ALFA", "discourse", ECO, -0.8, years=(2019, 2022)),
        evidence(RUBRIC, "d2", "ALFA", "discourse", SOC, 0.8, years=(2019, 2022)),
    ]
    document = classification_document(run(items))
    kinds = {(d["kind"], d["subject"]) for d in document["divergences"]}
    assert ("dimension", "economic") in kinds
    assert ("dimension", "sociocultural") not in kinds
    record = next(d for d in document["divergences"] if d["subject"] == "economic")
    assert record["gap"] > 0 and record["severity"] == "strong"
    assert "mais à direita do que declara" in record["explanation"]
    assert record["discourse_evidence_ids"] == ["d1"]
    assert ("indicator", ECO) in kinds


def test_no_divergence_when_discourse_matches_behavior():
    items = party_items("ALFA", 0.6, 0.6)
    items += [evidence(RUBRIC, "d1", "ALFA", "discourse", ECO, 0.5, years=(2019, 2022))]
    assert classification_document(run(items))["divergences"] == []


def test_self_declaration_is_compared_with_behavior_overall():
    items = party_items("ALFA", 0.8, 0.8)
    items.append(
        evidence(
            RUBRIC, "decl", "ALFA", "discourse", "self_declared_position", -0.7, years=(2019, 2022)
        )
    )
    document = classification_document(run(items))
    assert [d["kind"] for d in document["divergences"]] == ["self_declaration"]


def test_pdt_and_pcdob_share_one_pipeline_without_special_cases():
    """Contract: identical neutral inputs give identical outputs; no name-based rule exists."""
    pdt = classification_document(run(party_items("PDT", 0.1, -0.1), party="PDT"))
    pcdob = classification_document(run(party_items("PCdoB", 0.1, -0.1), party="PCdoB"))
    for document in (pdt, pcdob):
        for key in (
            "political_party",
            "political_party_id",
            "input_digest_sha256",
            "evidence_used",
            "explanation_by_indicator",
            "explanation_summary",
        ):
            document.pop(key)
    assert pdt == pcdob
    assert classification_document(run([], party="PDT"))["category"] == CATEGORY_INSUFFICIENT
    assert classification_document(run([], party="PCdoB"))["category"] == CATEGORY_INSUFFICIENT
