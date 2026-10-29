"""Contract validation: rubric, evidence and succession records (pure, no files)."""

import pytest
from party_orientation_fixtures import (
    FICTIONAL_SOURCE,
    evidence_document,
    evidence_entry,
    make_rubric,
    rubric_document,
)

from service.party_orientation_model.contracts import PartyModelContractError
from service.party_orientation_model.evidence import (
    parse_evidence_document,
    parse_evidence_item,
    parse_successions,
)
from service.party_orientation_model.rubric import parse_rubric

RUBRIC = make_rubric()


def entry(**changes):
    base = evidence_entry("e1", "ALFA", "votes", "economic_privatization", 0.5)
    return base | changes


def error_code(callable_, *arguments):
    with pytest.raises(PartyModelContractError) as raised:
        callable_(*arguments)
    return raised.value.code


def test_valid_rubric_exposes_weights_and_indicators():
    assert RUBRIC.rubric_version == "fixture-rubric.1"
    assert RUBRIC.indicators["economic_social_spending"].direction == -1
    assert [p.period_id for p in RUBRIC.periods] == ["2019-2022", "2023-2026"]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ({"schema_version": "other"}, "RUBRIC_SCHEMA_NOT_SUPPORTED"),
        (
            {"dimension_weights": {"economic": 0.6, "sociocultural": 0.6}},
            "RUBRIC_DIMENSION_WEIGHTS_MUST_SUM_TO_ONE",
        ),
        ({"band_limits": [-0.8, -0.5, 0.1, 0.0, 0.5, 0.8]}, "RUBRIC_BAND_LIMITS_NOT_INCREASING"),
        (
            {
                "proof_multipliers": {
                    "reported": 0.9,
                    "documented_secondary": 0.5,
                    "documented_primary": 1.0,
                }
            },
            "RUBRIC_PROOF_MULTIPLIERS_NOT_MONOTONIC",
        ),
        ({"discourse_cap_ratio": 1.0}, "RUBRIC_DISCOURSE_CAP"),
    ],
)
def test_rubric_rejects_invalid_documents(mutation, code):
    assert error_code(parse_rubric, rubric_document(**mutation)) == code


def test_rubric_rejects_scoring_expert_layer():
    weights = rubric_document()["layer_weights"] | {"expert_survey": 0.1}
    assert error_code(parse_rubric, rubric_document(layer_weights=weights)) == (
        "RUBRIC_EXPERT_LAYER_MUST_NOT_SCORE"
    )


def test_rubric_rejects_discourse_that_outweighs_behavior():
    weights = {"votes": 0.1, "discourse": 0.5, "expert_survey": 0.0}
    assert error_code(parse_rubric, rubric_document(layer_weights=weights)) == (
        "RUBRIC_BEHAVIOR_MUST_OUTWEIGH_DISCOURSE"
    )


def test_evidence_item_parses_with_source_and_date():
    item = parse_evidence_item(entry(), RUBRIC)
    assert item.source_url.startswith(FICTIONAL_SOURCE)
    assert item.source_date.isoformat() == "2021-03-01"


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"source_url": ""}, "EVIDENCE_SOURCE_REQUIRED"),
        ({"source_id": None}, "EVIDENCE_SOURCE_REQUIRED"),
        ({"source_date": "01/03/2021"}, "EVIDENCE_SOURCE_DATE_REQUIRED"),
        ({"stance": 1.5}, "EVIDENCE_STANCE_OUT_OF_RANGE"),
        ({"stance": True}, "EVIDENCE_STANCE_OUT_OF_RANGE"),
        ({"stance": float("nan")}, "EVIDENCE_STANCE_OUT_OF_RANGE"),
        ({"indicator_id": "unknown_indicator"}, "EVIDENCE_INDICATOR_NOT_IN_RUBRIC"),
        ({"dimension": "sociocultural"}, "EVIDENCE_INDICATOR_NOT_IN_RUBRIC"),
        ({"year_start": 2022, "year_end": 2019}, "EVIDENCE_VALIDITY_YEARS_INVALID"),
        ({"year_start": None}, "EVIDENCE_VALIDITY_YEARS_INVALID"),
        ({"proof_level": "rumor"}, "EVIDENCE_PROOF_LEVEL_INVALID"),
        ({"layer": "gossip"}, "EVIDENCE_LAYER_INVALID"),
        ({"attribution_basis": "guess"}, "EVIDENCE_ATTRIBUTION_BASIS_INVALID"),
    ],
)
def test_evidence_item_rejects_invalid_records(changes, code):
    assert error_code(parse_evidence_item, entry(**changes), RUBRIC) == code


def test_expert_survey_must_be_overall_reference():
    wrong = entry(layer="expert_survey")
    assert error_code(parse_evidence_item, wrong, RUBRIC) == "EVIDENCE_EXPERT_MUST_BE_OVERALL"


def test_overall_dimension_is_reserved_for_reference_layers():
    wrong = entry(dimension="overall", indicator_id="self_declared_position")
    assert error_code(parse_evidence_item, wrong, RUBRIC) == "EVIDENCE_OVERALL_ONLY_FOR_REFERENCE"


def test_duplicate_evidence_ids_are_rejected():
    document = evidence_document([entry(), entry()])
    assert error_code(parse_evidence_document, document, RUBRIC) == "EVIDENCE_ID_DUPLICATED"


def test_evidence_document_requires_known_schema():
    assert error_code(parse_evidence_document, {"schema_version": "x"}, RUBRIC) == (
        "EVIDENCE_SCHEMA_NOT_SUPPORTED"
    )


def succession(**changes):
    base = {
        "predecessor": "ANTIGO",
        "successor": "NOVO",
        "effective_date": "2022-02-01",
        "source_url": f"{FICTIONAL_SOURCE}/succession",
        "source_date": "2022-02-02",
    }
    return {"schema_version": "political_party_succession.v1", "successions": [base | changes]}


def test_succession_requires_source_and_date():
    assert parse_successions(succession())[0].successor == "NOVO"
    assert error_code(parse_successions, succession(source_url="")) == "SUCCESSION_SOURCE_REQUIRED"
    assert error_code(parse_successions, succession(effective_date="x")) == (
        "SUCCESSION_DATE_REQUIRED"
    )
    assert error_code(parse_successions, succession(successor="antigo")) == (
        "SUCCESSION_SAME_PARTY"
    )
