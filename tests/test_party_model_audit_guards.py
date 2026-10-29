"""Audit guarantees independent of any real political party's proposed label."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from party_orientation_fixtures import PERIOD_2019_2022, balanced_party_evidence, make_rubric

from application.party_orientation import _selected_parties
from service.party_orientation_model.batch import classify_many
from service.party_orientation_model.classifier import classify_party_period
from service.party_orientation_model.contracts import CATEGORY_INSUFFICIENT, PartyModelContractError
from service.party_vote_analysis.ideal_points import fit_ideal_points


def test_digest_covers_rubric_parameters_even_if_version_was_not_bumped():
    rubric = make_rubric()
    items = balanced_party_evidence(rubric, "ALFA", 0.5)
    changed = replace(rubric, discourse_cap_ratio=0.2)
    first = classify_party_period("ALFA", PERIOD_2019_2022, items, (), rubric)
    second = classify_party_period("ALFA", PERIOD_2019_2022, items, (), changed)
    assert first.input_digest != second.input_digest


def test_batch_builds_one_index_and_preserves_missing_parties(monkeypatch):
    import service.party_orientation_model.batch as batch

    rubric = make_rubric()
    items = balanced_party_evidence(rubric, "ALFA", 0.5)
    calls = []
    original = batch.index_evidence_by_party

    def count_index(evidence):
        calls.append(len(evidence))
        return original(evidence)

    monkeypatch.setattr(batch, "index_evidence_by_party", count_index)
    results = classify_many(["ALFA", "alfa", "BETA"], [PERIOD_2019_2022], items, (), rubric)
    assert calls == [len(items)]
    assert len(results) == 2
    missing = next(result for result in results if result.political_party_id == "beta")
    assert missing.category == CATEGORY_INSUFFICIENT
    assert missing.overall is None


def test_duplicate_evidence_cannot_inflate_sample_size():
    rubric = make_rubric()
    items = balanced_party_evidence(rubric, "ALFA", 0.5)
    with pytest.raises(PartyModelContractError, match="EVIDENCE_ID_DUPLICATED"):
        classify_many(["ALFA"], [PERIOD_2019_2022], (*items, items[0]), (), rubric)


def test_all_includes_documented_catalog_parties_without_coded_evidence(monkeypatch):
    monkeypatch.setattr("application.party_orientation._catalog_parties", lambda: ["ALFA", "BETA"])
    inputs = SimpleNamespace(evidence=(), successions=())
    assert _selected_parties(SimpleNamespace(all=True), inputs) == ["ALFA", "BETA"]


def test_member_without_observed_votes_is_missing_not_centrist():
    matrix = np.array([[1, -1, 1, -1]] * 6 + [[-1, 1, -1, 1]] * 6 + [[np.nan] * 4])
    fitted = fit_ideal_points(matrix, dimensions=1)
    assert np.isnan(fitted.scores[-1]).all()
    assert np.isfinite(fitted.scores[:-1]).all()


@pytest.mark.parametrize("dimensions", [0, -1, True, 1.5])
def test_invalid_pca_dimensions_are_rejected(dimensions):
    with pytest.raises(ValueError, match="positive integer"):
        fit_ideal_points(np.ones((12, 4)), dimensions)


def test_confidence_threshold_cannot_exceed_probability_scale():
    from party_orientation_fixtures import rubric_document

    from service.party_orientation_model.rubric import parse_rubric

    document = rubric_document()
    document["sufficiency"]["minimum_confidence"] = 1.5
    with pytest.raises(PartyModelContractError, match="RUBRIC_CONFIDENCE_RANGE"):
        parse_rubric(document)


def test_comparison_has_no_predefined_pdt_right_hypothesis():
    from service.party_orientation_model.comparison import DEFAULT_HYPOTHESES

    assert DEFAULT_HYPOTHESES == {}
