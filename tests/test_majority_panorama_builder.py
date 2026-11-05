"""Majority panorama data layer, with fictional in-memory sources (no database)."""

from datetime import date

import pytest

from service.majority_panorama.blocs import BLOC_KEYS
from service.majority_panorama.builder import build_majority_panorama
from service.majority_panorama.composition_source import is_reliable_record
from service.majority_panorama.legislature_windows import (
    legislature_windows,
    reference_year_candidates,
)
from service.majority_panorama.orientation_blocs import (
    UNREPORTED_PARTY_LABEL,
    classify_political_parties,
)
from service.majority_panorama.presidents import (
    PresidentialExercise,
    build_presidential_terms,
    presidents_in_legislature,
)

TODAY = date(2026, 11, 3)


def senate_record(parties, total=None, snapshot_on="2022-12-31"):
    groups = [{"abbreviation": name, "count": count} for name, count in parties]
    return {
        "institution_code": "senado", "territory_code": "BR", "snapshot_on": snapshot_on,
        "total": total if total is not None else sum(count for _, count in parties),
        "political_parties": groups, "coverage": "observed_complete",
    }


class FakeSource:
    def __init__(self, records=None, exercises=()):
        self.records, self.exercises = records or {}, exercises

    def annual_composition(self, house, year):
        return self.records.get((house, year))

    def presidency(self):
        return self.exercises


def test_windows_are_four_year_terms_with_dash_label():
    windows = legislature_windows(TODAY)
    assert windows[0].label == "1983–1986"
    assert windows[-1].label == "2023–2026"
    assert [w.first_year for w in windows][:3] == [1983, 1987, 1991]


def test_reference_years_try_newest_first_and_never_after_today():
    last = legislature_windows(TODAY)[-1]
    assert list(reference_year_candidates(last, date(2025, 5, 1)))[0] == 2025


def test_category_maps_to_bloc_and_sums_to_total():
    record = senate_record([("PT", 30), ("PL", 40), ("MDB", 11)])
    counts, by_bloc = classify_political_parties(record, 2022)
    assert set(counts) <= set(BLOC_KEYS)
    assert sum(counts.values()) == 81
    assert [party for party, _ in by_bloc["right"]][0] == "PL"
    assert counts["left"] == 30


def test_unclassified_party_is_undetermined_and_no_party_is_unaffiliated():
    record = senate_record([("PARTIDO FICTICIO", 5), ("S/Partido", 2), ("S.PART.", 1)])
    counts, _ = classify_political_parties(record, 2001)
    assert counts == {"undetermined": 5, "unaffiliated": 3}


def test_seats_without_party_fill_undetermined_with_explicit_label():
    record = senate_record([("PT", 10)], total=12)
    counts, by_bloc = classify_political_parties(record, 2022)
    assert counts["undetermined"] == 2
    assert by_bloc["undetermined"][0][0] == UNREPORTED_PARTY_LABEL


def test_unreliable_records_are_rejected():
    assert not is_reliable_record("senado", None)
    assert not is_reliable_record("senado", senate_record([("PT", 27)]))
    assert not is_reliable_record("senado", senate_record([("PT", 90)], total=80))
    assert is_reliable_record("senado", senate_record([("PT", 79)]))


def test_legislature_without_data_is_none_and_data_one_is_sampled_at_latest_year():
    records = {("senado", 2022): senate_record([("PT", 40), ("PL", 41)])}
    panorama = build_majority_panorama(FakeSource(records), TODAY)
    by_label = {item.label: item for item in panorama.legislatures}
    assert by_label["2019–2022"].senado.reference_year == 2022
    assert by_label["2019–2022"].senado.total == 81
    assert by_label["2019–2022"].camara is None
    assert by_label["1983–1986"].senado is None
    assert not by_label["2019–2022"].has_data
    assert "Senado em 31/12/2022" in panorama.sources_note
    assert any("Câmara sem composição" in note for note in panorama.coverage_notes)


def test_partial_coverage_note_is_kept_and_earlier_year_is_used():
    records = {
        ("senado", 2018): senate_record([("PT", 75)]),
        ("senado", 2017): senate_record([("PT", 81)]),
    }
    house = build_majority_panorama(FakeSource(records), TODAY).legislatures[8].senado
    assert house.reference_year == 2018
    assert any("Cobertura parcial: 75 de 81" in note for note in house.notes)


def exercise(person, name, start, end, parties=("PT",), exercise_id=None):
    return PresidentialExercise(
        exercise_id=exercise_id or f"{person}:{start}", person_id=person, full_name=name,
        starts_on=date.fromisoformat(start),
        ends_before=date.fromisoformat(end) if end else None, party_labels=parties,
    )


def test_presidents_by_legislature_merge_interim_and_mark_incumbent_end():
    exercises = (
        exercise("arquivo-nacional-president:205", "Dilma Fictícia", "2011-01-01", "2016-05-12"),
        exercise("arquivo-nacional-president:201", "Temer Fictício", "2016-05-12", "2016-08-31",
                 ("PMDB",)),
        exercise("arquivo-nacional-president:201", "Temer Fictício", "2016-08-31", "2019-01-01",
                 ("PMDB",)),
        exercise("arquivo-nacional-president:204", "Lula Fictício", "2023-01-01", None),
    )
    terms = build_presidential_terms(exercises, TODAY)
    assert [t.short_name for t in terms] == ["Dilma", "Temer", "Lula"]
    assert terms[2].end_on == date(2027, 1, 1) and terms[2].span_label == "2023–2026"
    assert terms[1].span_label == "2016–2018"
    windows = {w.label: w for w in legislature_windows(TODAY)}
    in_2015 = presidents_in_legislature(terms, windows["2015–2018"])
    assert [t.short_name for t in in_2015] == ["Dilma", "Temer"]
    assert terms[0].bloc_key == "left" and terms[1].bloc_key == "right"


def test_presidents_without_reviewed_evidence_are_undetermined_never_invented():
    unknown = exercise("pessoa:1", "Fulano Fictício", "2027-01-01", None, ())
    terms = build_presidential_terms((unknown,), date(2027, 3, 1))
    assert terms[0].bloc_key == "undetermined"
    assert terms[0].political_party_label == "sem partido"


def test_presidents_before_1985_are_not_listed():
    old = exercise("pessoa:2", "Antigo Fictício", "1979-03-15", "1985-03-15")
    assert build_presidential_terms((old,), TODAY) == ()


def test_missing_president_name_is_a_data_error():
    from service.majority_panorama.presidents import collect_presidential_exercises

    segment = {"exercise_id": "x:1", "person_id": "x", "starts_on": "2000-01-01",
               "ends_before": None, "political_party": "PT"}
    with pytest.raises(ValueError, match="PRESIDENT_NAME_MISSING"):
        collect_presidential_exercises({2000: [segment]}, {})
