from service.political_dashboard.presidential_explanations import (
    presidential_duration,
    presidential_year_explanation,
    presidential_year_label,
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


def test_acting_president_official_capacity_is_recognized():
    row = year_row(2000, [exercise("Pessoa", "1999-01-01", "2001-01-01",
                                  exercise_capacity="acting_president")])
    assert len(presidential_year_explanation(row)["interim"]) == 1


def test_short_duration_does_not_infer_impeachment():
    row = year_row(2000, [exercise("Pessoa", "2000-02-01", "2000-02-03")])
    result = presidential_year_explanation(row)
    assert presidential_duration(result["short"][0]) == 2
    assert result["events"] == []


def test_collective_junta_is_not_counted_as_one_individual_president():
    row = year_row(1969, [exercise("Costa", "1967-03-15", "1969-08-31"),
                         exercise("Junta", "1969-08-31", "1969-10-30",
                                  exercise_capacity="collective_junta"),
                         exercise("Médici", "1969-10-30", "1974-03-15")])
    result = presidential_year_explanation(row)
    assert result["people_count"] == 2
    assert result["collective_count"] == 1
    assert presidential_year_label(result).startswith(
        "3 governos registrados, incluindo governo coletivo"
    )


def test_documented_party_rename_is_an_event_without_claiming_migration():
    row = year_row(2018, [exercise("Pessoa", "2016-08-31", "2019-01-01")])
    result = presidential_year_explanation(row)
    assert "Renomeação da legenda" in [event[2] for event in result["events"]]


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
