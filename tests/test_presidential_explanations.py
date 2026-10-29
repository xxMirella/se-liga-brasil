from service.political_dashboard.presidential_explanations import (
    presidential_duration,
    presidential_year_explanation,
    render_presidential_explanations,
    render_presidential_markers,
)


def year_row(year, records):
    return {"year": year, "institutions": [{"institution_code": "presidency",
                                            "segments": records}]}


def exercise(name, start, end, **extra):
    return {"name": name, "person_id": name, "starts_on": start, "ends_before": end,
            "source_url": "https://www.gov.br/planalto/pt-br", **extra}


def test_same_person_interim_and_definitive_are_not_two_presidents():
    row = year_row(2016, [exercise("Dilma", "2015-01-01", "2016-05-12"),
                         exercise("Temer", "2016-05-12", "2016-08-31",
                                  exercise_capacity="interim_president"),
                         exercise("Temer", "2016-08-31", "2019-01-01")])
    result = presidential_year_explanation(row)
    assert result["people_count"] == 2
    assert len(result["interim"]) == 1
    assert len(result["events"]) == 2


def test_short_duration_does_not_infer_impeachment():
    row = year_row(2000, [exercise("Pessoa", "2000-02-01", "2000-02-03")])
    result = presidential_year_explanation(row)
    assert presidential_duration(result["short"][0]) == 2
    assert result["events"] == []
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert "impeachment" not in html
    assert "2 dias" in html


def test_unknown_or_year_precision_end_has_no_exact_duration():
    assert presidential_duration(exercise("Nome", "2000-01-01", None)) is None
    assert presidential_duration(exercise("Nome", "2000-01-01", "2001-01-01",
                                          date_precision="year")) is None


def test_full_multiyear_exercise_not_classified_short_from_annual_slice():
    row = year_row(2000, [exercise("Pessoa", "1999-01-01", "2003-01-01")])
    assert presidential_year_explanation(row) is None


def test_party_change_preserves_dates_without_counting_another_person():
    row = year_row(2021, [exercise("Pessoa", "2019-01-01", "2023-01-01",
                                  political_party_periods=[
                                      {"political_party": "Sem partido", "starts_on": "2021-01-01"},
                                      {"political_party": "PL", "starts_on": "2021-11-30"}])])
    result = presidential_year_explanation(row)
    assert result["people_count"] == 1
    assert result["political_party_changes"][0]["date"] == "2021-11-30"


def test_keyboard_click_markers_target_explanations_and_sources_open_new_tab():
    row = year_row(2000, [exercise("Pessoa", "2000-02-01", "2000-02-03")])
    marker = render_presidential_markers([row], [2000], 100, 10, 200)
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert 'href="/panorama?territory=BR&amp;year=2000#presidency-year-2000"' in marker
    assert 'id="presidency-year-2000"' in html
    assert '<summary>2000' in html
    assert 'target="_blank"' in html
    assert "noopener noreferrer" in html


def test_empty_or_other_geographic_scope_has_no_presidential_annotations():
    assert render_presidential_explanations({"level": "state", "history": []}) == ""
    assert render_presidential_explanations({"level": "federal", "history": []}) == ""


def test_collective_junta_is_not_counted_as_one_individual_president():
    row = year_row(1969, [exercise("Costa", "1967-03-15", "1969-08-31"),
                         exercise("Junta", "1969-08-31", "1969-10-30",
                                  exercise_capacity="collective_junta"),
                         exercise("Médici", "1969-10-30", "1974-03-15")])
    result = presidential_year_explanation(row)
    assert result["people_count"] == 2
    assert result["collective_count"] == 1
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert "3 governos registrados, incluindo governo coletivo" in html
    assert "3 pessoas" not in html


def test_acting_president_official_capacity_is_recognized():
    row = year_row(2000, [exercise("Pessoa", "1999-01-01", "2001-01-01",
                                  exercise_capacity="acting_president")])
    assert len(presidential_year_explanation(row)["interim"]) == 1


def test_selected_year_opens_its_explanation_after_marker_navigation():
    row = year_row(2000, [exercise("Pessoa", "2000-02-01", "2000-02-03")])
    html = render_presidential_explanations({"level": "federal", "year": 2000, "history": [row]})
    assert 'class="panorama-presidential-all-years" open' in html
    assert 'id="presidency-year-2000" class="panorama-presidential-year" open' in html


def test_unverified_gap_is_not_rendered_as_exact_day_of_party_change():
    row = year_row(2019, [exercise("Pessoa", "2019-01-01", "2023-01-01",
                                  political_party_periods=[
                                      {"political_party": "PSL", "starts_on": "2019-01-01",
                                       "ends_before": "2019-11-01"},
                                      {"political_party": "Sem partido",
                                       "starts_on": "2019-12-01"}])])
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert "Registro a partir de 2019-12-01" in html
    assert "a data não indica o dia da troca" in html


def test_documented_party_rename_explains_change_without_claiming_migration():
    row = year_row(2018, [exercise("Pessoa", "2016-08-31", "2019-01-01")])
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert "Renomeação da legenda" in html
    assert "decisão do TSE" in html


def test_1966_support_context_is_visible_without_becoming_presidential_affiliation():
    from copy import deepcopy

    from service.political_dashboard.page import render_executive
    from service.political_dashboard.timeline import executive_cell

    record = exercise(
        "Castelo Branco", "1964-04-15", "1967-03-15", date_precision="day",
        political_party="Filiação histórica não verificada", political_party_status="unknown",
    )
    row = year_row(1966, [record])
    institution = row["institutions"][0]
    institution.update(current=record, government_context_observations=[{
        "date": "1966-03-24", "title": "Registro da organização governista",
        "organization": "ARENA",
        "relationship": "government_support_organization_not_personal_affiliation",
        "summary": (
            "A ARENA foi registrada como organização em 24/03/1966. "
            "Isso não comprova a filiação pessoal do presidente."
        ),
        "source_url": "https://www.tse.jus.br/partidos/partidos-registrados-no-tse/historico/"
                      "registros-de-partidos-politicos-1945-a-1979-1/alianca-renovadora-nacional",
    }])
    original = deepcopy(institution)
    explanation = presidential_year_explanation(row)
    assert explanation["political_party_changes"] == []
    assert executive_cell(institution)["state"] == "unknown"
    executive_html = render_executive(institution, "Presidência", "Poder Executivo")
    assert "ARENA" not in executive_html
    assert "Filiação histórica não verificada" in executive_html
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert "Registro da organização governista" in html
    assert "ARENA" in html
    assert "não comprova a filiação pessoal" in html
    assert "Apoio ao governo e filiação pessoal são informações diferentes." in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert institution == original
    marker = render_presidential_markers([row], [1966], 100, 10, 200)
    assert "contexto partidário documentado" in marker
    assert "mudança na atribuição partidária" not in marker


def test_1955_causes_preserve_distinct_interim_impediment_and_confirmation_dates():
    row = year_row(1955, [exercise("Café Filho", "1954-08-24", "1955-11-08"),
                         exercise("Carlos Luz", "1955-11-08", "1955-11-11",
                                  exercise_capacity="acting_president"),
                         exercise("Nereu Ramos", "1955-11-11", "1956-01-31")])
    explanation = presidential_year_explanation(row)
    assert [(event[1], event[2]) for event in explanation["events"]] == [
        ("1955-11-08", "Substituição interina"),
        ("1955-11-11", "Impedimento e sucessão"),
        ("1955-11-22", "Confirmação até a posse do eleito"),
    ]
    html = render_presidential_explanations({"level": "federal", "history": [row]})
    assert "O Congresso declarou Carlos Luz impedido" in html
    assert "afastamento definitivo de Café Filho" in html
    assert "confirmou Nereu Ramos" in html
    assert "impeachment" not in html.lower()
