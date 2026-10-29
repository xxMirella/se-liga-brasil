from datetime import date

import numpy as np
import pytest

from service.party_vote_analysis.choices import Choice, parse_choice, scalar_value
from service.party_vote_analysis.contracts import PropositionRef, VoteRecord
from service.party_vote_analysis.government_alignment import (
    government_agreement,
    orientation_map,
    party_majority,
)
from service.party_vote_analysis.ideal_points import align_to_reference, fit_ideal_points
from service.party_vote_analysis.legislatures import government_on, legislature_of
from service.party_vote_analysis.member_matrix import build_matrix
from service.party_vote_analysis.merit_selection import (
    is_camara_main_text_vote,
    is_senate_main_text_vote,
)
from service.party_vote_analysis.party_metrics import cohesion_by_party, rice_index, tally_votes
from service.party_vote_analysis.thematic_catalog import CATALOG
from service.party_vote_analysis.thematic_matching import match_thematic_items
from service.party_vote_analysis.thematic_scores import ItemCounts, dimension_score


def vote(voting, member, party, choice):
    return VoteRecord("camara", voting, date(2019, 7, 10), member, party, "SP", choice)


def test_choices_are_not_collapsed():
    assert parse_choice("Não") is Choice.NO
    assert parse_choice("Obstrução") is Choice.OBSTRUCTION
    assert parse_choice("Artigo 17") is Choice.PRESIDING
    assert parse_choice("AP") is Choice.OTHER
    assert scalar_value(Choice.ABSTENTION) is None and scalar_value(Choice.YES) == 1


def test_merit_rule_accepts_base_text_and_rejects_requirements():
    assert is_camara_main_text_vote(
        "Aprovado o Projeto de Lei nº 4.162, de 2019, ressalvados os destaques."
    )
    assert is_camara_main_text_vote(
        "Aprovada a Proposta de Emenda à Constituição nº 6, de 2019, em segundo turno."
    )
    assert not is_camara_main_text_vote("Rejeitado o Requerimento. Sim: 10; não: 200.")
    assert not is_camara_main_text_vote("Rejeitada a Emenda nº 15. Sim: 85; Não: 314.")
    assert not is_camara_main_text_vote("Mantido o texto. Sim: 258; não: 158.")
    assert is_senate_main_text_vote("PEC", "PEC nº 6, de 2019 (1º Turno)")
    assert not is_senate_main_text_vote("REQ", "Requerimento nº 1")
    assert not is_senate_main_text_vote("PL", "Emenda nº 3 ao Projeto")


def test_catalog_signs_and_indicators_are_explicit():
    assert len({item.item_id for item in CATALOG}) == len(CATALOG)
    for item in CATALOG:
        assert item.yes_sign in (-1, 1) and item.ementa_guard and item.rationale
        assert item.indicator_id[0] in "EC"


def test_thematic_match_needs_identity_and_ementa_guard():
    right = PropositionRef("PEC", 241, 2016, "Institui o Novo Regime Fiscal no âmbito da União")
    wrong_text = PropositionRef("PEC", 241, 2016, "Altera a organização do Judiciário")
    assert [i.item_id for i in match_thematic_items("camara", [right])] == ["teto_gastos_2016"]
    assert match_thematic_items("camara", [wrong_text]) == []
    assert match_thematic_items("senado", [PropositionRef("PEC", 99, 2016, "regime fiscal")]) == []


def test_rice_and_cohesion_use_vote_time_party():
    votes = [vote("v1", str(i), "AAA", Choice.YES) for i in range(5)]
    votes += [vote("v1", str(10 + i), "BBB", Choice.YES if i < 3 else Choice.NO) for i in range(6)]
    votes += [vote("v1", "99", "BBB", Choice.OBSTRUCTION)]
    summary = cohesion_by_party(tally_votes(votes))
    assert summary["AAA"]["rice_index_mean"] == 1.0
    assert summary["BBB"]["rice_index_mean"] == pytest.approx(0.0)
    assert summary["BBB"]["obstruction_rate"] == pytest.approx(1 / 7)
    assert rice_index(3, 1) == 0.5


def test_party_switcher_becomes_two_rows():
    votes = [vote(f"v{k}", "7", "OLD" if k < 3 else "NEW", Choice.YES) for k in range(6)]
    matrix = build_matrix(votes, minimum_votes_per_row=3)
    assert sorted(matrix.row_keys) == [("7", "NEW"), ("7", "OLD")]


def synthetic_matrix(rng, per_group=30, rolls=60):
    group = np.repeat([0, 1], per_group)
    truth = np.where(rng.random(rolls) < 0.5, 1, -1)
    base = np.where(group[:, None] == 0, truth, -truth).astype(float)
    flips = rng.random(base.shape) < 0.05
    values = np.where(flips, -base, base)
    values[rng.random(values.shape) < 0.2] = np.nan
    return group, values


def test_ideal_points_separate_two_blocs_and_alignment_fixes_sign():
    group, values = synthetic_matrix(np.random.default_rng(1))
    fit = fit_ideal_points(values, 2)
    first = fit.scores[:, 0]
    assert abs(first[group == 0].mean() - first[group == 1].mean()) > 2 * first.std() * 0.5
    assert fit.explained_variance_share[0] > 0.5
    flipped = align_to_reference(fit.scores, -fit.scores)
    assert np.allclose(flipped, fit.scores)


def test_ideal_points_reject_tiny_input():
    with pytest.raises(ValueError):
        fit_ideal_points(np.array([[1.0, -1.0], [1.0, -1.0]]), 2)


def test_dimension_score_orients_by_pole_and_has_interval():
    items = [ItemCounts("E1", 1, 90, 10), ItemCounts("E1", -1, 10, 90), ItemCounts("E4", 1, 80, 20)]
    result = dimension_score(items)
    assert result["value"] > 0.6 and result["ci95"][0] <= result["value"] <= result["ci95"][1]
    assert result["n_indicators"] == 2
    assert dimension_score([ItemCounts("E1", 1, 1, 1)]) is None


def test_government_alignment_uses_majority_and_period():
    votes = [vote("v1", str(i), "AAA", Choice.YES) for i in range(6)]
    tallies = tally_votes(votes)
    mapping = orientation_map(
        [
            {"voting_id": "v1", "bloc": "Governo", "orientation": "Sim"},
            {"voting_id": "v1", "bloc": "Governo", "orientation": "Liberado"},
        ]
    )
    assert party_majority(tallies[("v1", "AAA")]) is Choice.YES
    result = government_agreement(tallies, mapping, {"v1": date(2019, 7, 10)})
    assert result[("AAA", "Bolsonaro")] == [1, 1]
    assert government_on(date(2016, 5, 12)) == "Temer"
    assert legislature_of(2019).number == 56
