import pytest

from service.political_dashboard.orientation_timeline import executive_orientation_cell
from service.political_dashboard.timeline import timeline_cell


def presidency(exercise_id, political_party="Sem partido"):
    return {"institution_code": "presidency", "segments": [{
        "exercise_id": exercise_id, "political_party": political_party,
        "political_party_status": "verified_period",
    }]}


def test_government_evidence_does_not_depend_on_party_affiliation():
    institution = presidency("arquivo-nacional-president:199:2019-01-01")
    row = {"year": 2020, "institutions": [institution]}
    assert timeline_cell(row, "presidency", "executive")["label"] == "Sem partido"
    cell = timeline_cell(row, "presidency", "executive", "political_orientation")
    assert cell["label"] == "Extrema direita"
    assert cell["source_evidence"][0]["source_publication_year"] == 2025
    assert institution["segments"][0]["political_party"] == "Sem partido"


def test_regime_year_boundaries_remain_partial_and_do_not_classify_other_executives():
    for year in (1964, 1985):
        cell = executive_orientation_cell({"institution_code": "presidency"}, year)
        assert cell["label"] == "Direita · ditadura · parte do ano"
        assert "O restante deste ano não recebe" in cell["detail"]
    whole = executive_orientation_cell({"institution_code": "presidency"}, 1966)
    assert whole["label"] == "Direita · ditadura"
    other = executive_orientation_cell({"institution_code": "state_government"}, 1966)
    assert other["label"] == "Sem classificação"


def test_lula_current_mandate_keeps_editorial_and_coalition_qualification():
    institution = presidency("arquivo-nacional-president:204:2023-01-01", "PT")
    cell = executive_orientation_cell(institution, 2026)
    assert cell["label"] == "Esquerda"
    assert "não é medição acadêmica anual" in cell["detail"]
    assert "conciliação entre classes" in cell["detail"]
    future = executive_orientation_cell(institution, 2027)
    assert future["label"] == "Sem classificação"


def test_unknown_exercise_does_not_receive_presidents_classification_by_name():
    institution = presidency("unverified-source:199")
    institution["segments"][0]["name"] = "Jair Bolsonaro"
    assert executive_orientation_cell(institution, 2020)["label"] == "Sem filiação"


def test_dilma_and_temer_transition_keeps_both_governments_visible():
    institution = presidency("arquivo-nacional-president:205:2011-01-01", "PT")
    institution["segments"].append({"exercise_id": "arquivo-nacional-president:201:2016-05-12"})
    cell = executive_orientation_cell(institution, 2016)
    assert cell["label"] == "Esquerda / Direita"
    assert "até 12/05" in cell["detail"]
    assert "2016-05-12 até 2016-08-31" in cell["detail"]


@pytest.mark.parametrize("year", range(2011, 2016))
def test_every_dilma_full_year_is_left_in_the_timeline(year):
    institution = presidency("arquivo-nacional-president:205:2011-01-01", "PT")
    cell = timeline_cell({"year": year, "institutions": [institution]},
                         "presidency", "executive", "political_orientation")
    assert cell["label"] == "Esquerda"


@pytest.mark.parametrize("year", [2017, 2018])
def test_temer_governs_until_end_of_2018_despite_election(year):
    institution = presidency("arquivo-nacional-president:201:2016-08-31", "MDB")
    institution["segments"].append({
        "exercise_id": "arquivo-nacional-president:199:2019-01-01",
        "starts_on": "2019-01-01", "ends_before": "2023-01-01",
    })
    cell = timeline_cell({"year": year, "institutions": [institution]},
                         "presidency", "executive", "political_orientation")
    assert cell["label"] == "Direita"
    assert "Bolsonaro" not in cell["detail"]


@pytest.mark.parametrize("year", range(2019, 2023))
def test_every_bolsonaro_government_year_is_far_right(year):
    institution = presidency("arquivo-nacional-president:199:2019-01-01")
    cell = timeline_cell({"year": year, "institutions": [institution]},
                         "presidency", "executive", "political_orientation")
    assert cell["label"] == "Extrema direita"


def test_legacy_projection_uses_exact_person_and_exercise_start_not_name():
    institution = {"institution_code": "presidency", "segments": [{
        "person_id": "arquivo-nacional-president:205", "starts_on": "2011-01-01",
        "ends_before": "2016-05-12", "name": "nome não utilizado",
    }]}
    assert executive_orientation_cell(institution, 2015)["label"] == "Esquerda"
    institution["segments"][0]["person_id"] = "unverified:205"
    assert executive_orientation_cell(institution, 2015)["label"] == "Sem classificação"


def test_2016_details_keep_acting_and_definitive_exercises_separate():
    from service.political_dashboard.executive_orientation_presentation import (
        render_executive_orientation,
    )

    institution = presidency("arquivo-nacional-president:205:2011-01-01", "PT")
    institution["segments"] += [
        {"exercise_id": "arquivo-nacional-president:201:2016-05-12"},
        {"exercise_id": "arquivo-nacional-president:201:2016-08-31"},
    ]
    cell = executive_orientation_cell(institution, 2016)
    assert cell["label"] == "Esquerda / Direita"
    assert [(row["coverage_start"], row["coverage_end_exclusive"])
            for row in cell["source_evidence"]] == [
        ("2016-01-01", "2016-05-12"),
        ("2016-05-12", "2016-08-31"),
        ("2016-08-31", "2017-01-01"),
    ]
    html = render_executive_orientation(institution, "political_orientation", 2016)
    assert "Esquerda / Direita" in html
    assert "2016-05-12 até 2016-08-31" in html


@pytest.mark.parametrize("year", range(1995, 2003))
def test_every_fhc_year_is_center_right_government_not_party_inference(year):
    starts_on = "1995-01-01" if year < 1999 else "1999-01-01"
    institution = presidency("arquivo-nacional-president:197:" + starts_on, "PSDB")
    cell = timeline_cell({"year": year, "institutions": [institution]},
                         "presidency", "executive", "political_orientation")
    assert cell["label"] == "Direita"
    assert "Centro-direita" in cell["detail"]
    assert "Bolsa Escola" in cell["detail"]
    assert "não é extrema direita" in cell["detail"]


def test_fhc_detail_exposes_academic_documents_and_counterevidence():
    from service.political_dashboard.executive_orientation_presentation import (
        render_executive_orientation,
    )

    institution = presidency("arquivo-nacional-president:197:1999-01-01", "PSDB")
    html = render_executive_orientation(institution, "political_orientation", 2002)
    assert "Bolsa Escola" in html
    assert "Plano Diretor" in html
    assert "Privatização — Federais — Telecomunicações" in html
    assert "None" not in html
    assert html.count('https://www.scielo.br/j/ts/') == 1


def test_fhc_does_not_leak_into_lula_succession():
    institution = presidency("arquivo-nacional-president:204:2003-01-01", "PT")
    institution["segments"].append({
        "exercise_id": "arquivo-nacional-president:197:1999-01-01",
        "starts_on": "1999-01-01", "ends_before": "2003-01-01",
    })
    assert executive_orientation_cell(institution, 2003)["label"] == "Esquerda"
