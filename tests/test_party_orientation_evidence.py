"""Conversion of collected layers to party_orientation_evidence.v1 (fictional inputs only)."""

import json
from datetime import date
from pathlib import Path

import pytest
from party_orientation_fixtures import make_rubric

from service.party_orientation_evidence.discourse import self_declaration_records
from service.party_orientation_evidence.expert import (
    bolognesi_records,
    scaled_stance,
    zucco_records,
)
from service.party_orientation_evidence.policies import governing_party, legal_act_records
from service.party_orientation_evidence.records import evidence_document
from service.party_orientation_evidence.votes import (
    decided_parties,
    pole_stance,
    procedural_voting_ids,
    thematic_vote_records,
)
from service.party_orientation_model.contracts import PartyModelContractError
from service.party_orientation_model.evidence import parse_evidence_document
from service.party_orientation_model.rubric import parse_rubric
from service.party_orientation_model.rubric_adapter import (
    _indicator_weight,
    adapt_proposal_to_rubric_document,
)

RUBRIC = make_rubric()
ECONOMIC = "economic_privatization"
SOCIAL = "sociocultural_civil_rights"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def roll_call(
    voting_id, indicator, yes_sign=1, voted_on="2020-05-05", description="Aprovado o projeto."
):
    return {
        "voting_id": voting_id,
        "item_id": f"item-{voting_id}",
        "theme": "tema fictício",
        "indicator_id": indicator,
        "yes_sign": yes_sign,
        "voted_on": voted_on,
        "description": description,
        "rationale": "justificativa fictícia.",
    }


def block(*roll_calls, chamber="camara"):
    return {
        "chamber": chamber,
        "thematic_roll_calls": list(roll_calls),
        "government_alignment": [
            {"party": "ALFA", "government": "G", "agreement": 0.5, "n_roll_calls": 10}
        ],
    }


def lookup(chamber, year):
    return f"https://example.invalid/{chamber}/{year}"


def test_pole_stance_follows_the_yes_sign_not_the_party():
    assert pole_stance(9, 1, +1) == pytest.approx(0.8)
    assert pole_stance(9, 1, -1) == pytest.approx(-0.8)
    assert pole_stance(5, 5, +1) == 0


def test_only_parties_with_enough_decided_votes_and_a_party_label_count():
    counts = {
        "ALFA": {"sim": 3, "nao": 0},
        "BETA": {"sim": 2, "nao": 0},
        "S.PART.": {"sim": 9, "nao": 9},
    }
    assert set(decided_parties(counts)) == {"ALFA"}


def test_vote_records_are_validated_by_the_evidence_contract():
    tallies = {f"v{i}": {"ALFA": {"sim": 8, "nao": 2}} for i in range(3)}
    rolls = [roll_call(f"v{i}", ECONOMIC) for i in range(3)]
    records = thematic_vote_records(block(*rolls), tallies, lookup, RUBRIC)
    items = parse_evidence_document(
        evidence_document("votes", records, [], date(2026, 10, 29)), RUBRIC
    )
    assert len(items) == 3
    first = items[0]
    assert first.layer == "votes" and first.proof_level == "documented_primary"
    assert first.stance == pytest.approx(0.6) and first.source_url == lookup("camara", 2020)
    assert first.attribution_basis == "member_votes_by_affiliation_at_vote_date"
    assert first.human_reviewed is False


def test_fewer_than_three_thematic_votings_in_a_dimension_are_only_indicative():
    tallies = {
        "v1": {"ALFA": {"sim": 8, "nao": 2}},
        "v2": {"ALFA": {"sim": 8, "nao": 2}},
        "v3": {"ALFA": {"sim": 1, "nao": 9}},
    }
    rolls = [roll_call("v1", ECONOMIC), roll_call("v2", ECONOMIC), roll_call("v3", SOCIAL)]
    records = thematic_vote_records(block(*rolls), tallies, lookup, RUBRIC)
    assert {r["proof_level"] for r in records} == {"reported"}
    assert all("Indicativo" in r["description"] for r in records)


def test_coalition_years_are_flagged_and_government_alignment_is_described():
    tallies = {"v1": {"ALFA": {"sim": 8, "nao": 2}}}
    records = thematic_vote_records(
        block(roll_call("v1", ECONOMIC, voted_on="2008-03-03")), tallies, lookup, RUBRIC
    )
    description = records[0]["description"]
    assert "coalizões heterogêneas" in description and "50%" in description
    assert "sem eixo de PCA" in description


@pytest.mark.parametrize(
    ("president_party", "government", "expected"),
    [
        ("PT", "Lula I", "PT"),
        ("PSL (filiado até 11/2019)", "Bolsonaro", "PSL"),
        ("sem partido (11/2019 a 11/2021)", "Bolsonaro", None),
        ("PMDB", "Itamar (coalizão)", None),
    ],
)
def test_governing_party_credits_only_a_single_party_government(
    president_party, government, expected
):
    act = {"president_party": president_party, "government": government}
    assert governing_party(act) == expected


def act(identifier, direction, president_party="ALFA", government="G1"):
    return {
        "id": identifier,
        "urn": f"urn:fictional:{identifier}",
        "date": "2020-06-01",
        "president_party": president_party,
        "government": government,
        "rubric_indicator": ECONOMIC,
        "proposed_direction": direction,
        "topic": "ato fictício",
    }


def test_legal_acts_need_verification_direction_and_a_single_party():
    acts = [act("a1", -1), act("a2", None), act("a3", 1), act("a4", 1, "sem partido (x)")]
    verification = {
        "a1": {"status": "verificado", "url": "https://example.invalid/a1"},
        "a2": {"status": "verificado", "url": "https://example.invalid/a2"},
        "a4": {"status": "verificado", "url": "https://example.invalid/a4"},
    }
    records, skipped = legal_act_records(acts, verification, RUBRIC)
    assert [r["evidence_id"] for r in records] == ["implemented:a1"]
    assert records[0]["proof_level"] == "documented_secondary"
    assert records[0]["attribution_basis"] == "party_in_government"
    assert skipped == {
        "a2": "direcao_nao_codificada",
        "a3": "ato_nao_verificado_no_lexml",
        "a4": "ato_sem_partido_unico_do_presidente_ou_governo_de_coalizao",
    }


def test_expert_scales_map_to_the_minus_one_plus_one_axis():
    assert scaled_stance(0, 5.0, 5.0) == -1 and scaled_stance(10, 5.0, 5.0) == 1
    assert scaled_stance(1, 5.5, 4.5) == -1 and scaled_stance(5.5, 5.5, 4.5) == 0


def test_expert_records_are_overall_references_with_the_surveys_own_label():
    catalog = [
        {
            "political_party": "PR",
            "reference_year": 2018,
            "score": 7.5,
            "respondents": 10,
            "source_column": "ideol_18_pr",
            "source_url": "https://example.invalid/bolognesi",
            "methodology_id": "bolognesi_expert_mean_0_10_v1",
        },
        {"political_party": "X", "methodology_id": "other"},
    ]
    records = bolognesi_records(catalog) + zucco_records({"PPB": {1997: 6.1, 1980: 3.0}})
    assert [r["political_party"] for r in records] == ["PR", "PPB"]
    assert all(r["layer"] == "expert_survey" and r["dimension"] == "overall" for r in records)
    assert records[0]["stance"] == pytest.approx(0.5)


def party_document(quote):
    return {
        "documentos_obtidos": [
            {
                "url": "https://example.invalid/doc",
                "sha256": "a" * 64,
                "rotulo_declarado_candidatos": [{"trecho": quote}],
                "temas": {"economia_estado": []},
            }
        ]
    }


def review(prefix):
    return {
        "review_id": "r1",
        "political_party": "ALFA",
        "document_url": "https://example.invalid/doc",
        "quote_prefix": prefix,
        "stance": 1.0,
        "reading": "leitura fictícia",
        "year": 2025,
        "source_date": "2025-01-01",
    }


def test_self_declaration_requires_the_quote_to_exist_in_the_archive():
    documents = {"alfa": party_document("Somos o partido mais à direita.")}
    records = self_declaration_records([review("Somos o partido")], documents)
    assert records[0]["layer"] == "discourse" and records[0]["human_reviewed"] is False
    assert records[0]["indicator_id"] == "self_declared_position"
    with pytest.raises(PartyModelContractError) as error:
        self_declaration_records([review("Citação inexistente")], documents)
    assert error.value.code == "DISCOURSE_QUOTE_NOT_IN_ARCHIVE"


def test_contested_indicator_weight_is_overridden_only_when_approved():
    contested = {"weight_modifier": 0.5, "contested_direction": True}
    plain = {"weight_modifier": 1.0, "contested_direction": False}
    assert _indicator_weight(contested, 0.0) == 0.0
    assert _indicator_weight(contested, None) == 0.5
    assert _indicator_weight(plain, 0.0) == 1.0


def test_approved_rubric_scores_only_indicators_with_uncontested_direction():
    path = PROJECT_ROOT / "data/political-orientation/party-model/rubric.json"
    if not path.exists():
        pytest.skip("rubric.json não existe neste ambiente")
    raw = json.loads(path.read_text())
    assert (
        raw["approval"]["status"] == "APROVADA" and raw["approval"]["approved_on"] == "2026-10-29"
    )
    assert {d["id"] for d in raw["approval"]["decisions"]} == {f"R{n}" for n in range(1, 9)}
    rubric = parse_rubric(adapt_proposal_to_rubric_document(raw))
    contested = {"E5", "E7", "E9", "C3", "C5", "C7", "C8"}
    for indicator_id, indicator in rubric.indicators.items():
        expected_zero = indicator_id.split("_")[0] in contested
        assert (indicator.weight == 0) is expected_zero
    assert rubric.layer_weights.get("expert_survey", 0) == 0


def test_procedural_requests_are_not_converted_into_policy_positions():
    tallies = {
        "v1": {"ALFA": {"sim": 8, "nao": 2}},
        "v2": {"ALFA": {"sim": 8, "nao": 2}},
    }
    rolls = [
        roll_call("v1", ECONOMIC),
        roll_call("v2", ECONOMIC, description="Votação nominal do Requerimento de preferência."),
    ]
    records = thematic_vote_records(block(*rolls), tallies, lookup, RUBRIC)
    assert [r["evidence_id"] for r in records] == ["votes:camara:v1:alfa"]
    assert procedural_voting_ids([block(*rolls)]) == ["camara:v2"]
