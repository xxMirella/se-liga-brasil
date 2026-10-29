"""Chamber majority is national, dated, auditable and independent of classified coverage."""

import hashlib
import json
from datetime import date

import pytest

from crawlers.camara.dated_roster import load_dated_roster
from crawlers.camara.historical_exercises import resolve_simultaneous_summons
from crawlers.camara.legacy_exercises import corroborated_legacy_entry
from service.political_dashboard.camara_orientation import (
    chamber_orientation,
    chamber_orientation_summary,
    render_chamber_orientation_summary,
)
from service.political_dashboard.orientation_composition import orientation_composition
from service.political_dashboard.timeline import timeline_cell
from service.political_dashboard_dataset.chamber_changes import dated_chamber_changes
from service.political_dashboard_dataset.history import reduce_composition


def chamber(groups, total=None):
    return {"institution_code": "camara", "territory_code": "BR", "expected_seats": 513,
            "orientation_policy_version": "camara_2020_2026.v1",
            "snapshot_on": "2026-10-29", "coverage": "observed_partial",
            "total": sum(groups.values()) if total is None else total,
            "political_parties": [{"abbreviation": name, "count": count}
                                  for name, count in groups.items()]}


def test_partial_classified_subset_cannot_create_absolute_majority():
    summary = chamber_orientation_summary(chamber({"PL": 200, "PT": 100}), 2026)
    assert summary["absolute_majority"] is None
    assert summary["majority_threshold"] == 257
    assert summary["unobserved_seats"] == 213
    assert summary["absence_proven"] is False


def test_majority_is_proven_even_when_unclassified_seats_are_adversarial():
    summary = chamber_orientation_summary(chamber({"PL": 257, "PT": 200, "NEW": 56}), 2026)
    assert summary["absolute_majority"] == "right"
    assert summary["counts"]["undetermined"] == 56
    assert summary["classified_people"] == 457


def test_no_majority_is_distinct_from_insufficient_evidence():
    summary = chamber_orientation_summary(chamber({"PL": 256, "PT": 256, "S.PART.": 1}), 2026)
    assert summary["absolute_majority"] is None
    assert summary["absence_proven"] is True
    assert summary["largest_groups"] == ["left", "right"]


def test_scope_and_capacity_cannot_be_inferred_from_observed_total():
    data = chamber({"PL": 513})
    data.pop("expected_seats")
    assert chamber_orientation_summary(data, 2026) is None
    data["expected_seats"] = 513
    data["territory_code"] = "SP"
    assert chamber_orientation_summary(data, 2026) is None


def test_editorial_policy_does_not_mutate_original_catalog_or_inherit_mergers():
    from service.political_dashboard.political_orientation_catalog import (
        classify_political_orientation,
    )

    assert classify_political_orientation("PT", 2020)["category"] == "undetermined"
    assert chamber_orientation({"abbreviation": "PT"}, 2020)["reference_year"] == 2018
    assert chamber_orientation({"abbreviation": "PV"}, 2020)["category"] == "center"
    assert chamber_orientation({"abbreviation": "PV"}, 2026)["category"] == "left"
    assert chamber_orientation({"abbreviation": "PRD"}, 2026)["category"] == "undetermined"
    assert chamber_orientation({"abbreviation": "MISSÃO"}, 2026)["category"] == "undetermined"
    assert chamber_orientation({"abbreviation": "PODE"}, 2022)["category"] == "right"
    assert chamber_orientation({"abbreviation": "PL"}, 2020)["category"] == "undetermined"
    unknown = {"abbreviation": "PL", "political_party_code": "unreconciled"}
    assert chamber_orientation(unknown, 2026)["category"] == "undetermined"


def test_chart_timeline_and_original_party_counts_remain_consistent():
    data = chamber({"PL": 300, "PT": 200, "PRD": 13})
    chart = orientation_composition(data, 2026)
    assert sum(row["count"] for row in chart["political_parties"]) == 513
    cell = timeline_cell({"year": 2026, "institutions": [data]}, "camara", "legislative",
                         "political_orientation")
    assert "maioria absoluta" in cell["label"]
    assert "257/513" in cell["detail"]
    assert "Survey de 2022" in cell["detail"]
    html = render_chamber_orientation_summary(data, 2026)
    assert "PRD: 13 · Sem classificação" in html
    assert "onda 2018" in html and "onda 2022" in html
    assert data["political_parties"][0]["abbreviation"] == "PL"
    reduced = reduce_composition({"institution_code": "camara", "composition": data})
    assert reduced["expected_seats"] == 513


def test_party_count_remainder_and_invalid_capacity():
    data = chamber({"PL": 257}, total=513)
    assert chamber_orientation_summary(data, 2026)["counts"]["undetermined"] == 256
    with pytest.raises(ValueError, match="CAPACITY"):
        chamber_orientation_summary(chamber({"PL": 514}), 2026)
    with pytest.raises(ValueError, match="COUNTS_EXCEED"):
        chamber_orientation_summary(chamber({"PL": 3}, total=2), 2026)


def test_summons_same_time_entry_is_resolved_but_departure_or_party_conflict_is_not():
    entry = {"situacao": "Exercício", "descricaoStatus": "Entrada - Reassunção",
             "siglaPartido": "PT", "siglaUf": "BA"}
    summons = dict(entry, situacao="CONVOCADO", descricaoStatus="DIVERSO - Convocação")
    assert resolve_simultaneous_summons([summons, entry]) == [entry]
    departure = dict(entry, situacao="Licença")
    assert resolve_simultaneous_summons([entry, departure]) == [entry, departure]
    other_party = dict(summons, siglaPartido="PL")
    assert resolve_simultaneous_summons([entry, other_party]) == [entry, other_party]
    assert resolve_simultaneous_summons([summons]) == [summons]


def test_legacy_period_proves_exercise_without_using_current_party():
    event = {"idLegislatura": 56, "dataHora": "2019-10-30T16:14", "situacao": "CONVOCADO",
             "descricaoStatus": "Entrada - Reassunção / DIVERSO - Convocação Eleito ou Suplente",
             "siglaUf": "BA", "siglaPartido": "PT"}
    history = {"events": [event]}
    record = {"legislature": 56, "periods": [{"starts_on": date(2019, 10, 30),
                                              "ends_on": date(2023, 1, 31), "uf": "BA"}]}
    assert corroborated_legacy_entry(history, record, 2020)["siglaPartido"] == "PT"
    assert corroborated_legacy_entry(history, record, 2023) is None
    record["periods"][0]["ends_on"] = date(2020, 12, 31)
    assert corroborated_legacy_entry(history, record, 2020) is None


def archive_page(tmp_path, document, url, fetched_at="2026-10-29T18:00:00+00:00"):
    raw = json.dumps(document).encode()
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / (digest + ".json")).write_bytes(raw)
    evidence = {"url": url, "sha256": digest, "fetched_at": fetched_at}
    (tmp_path / "sources.json").write_text(json.dumps([evidence]))
    return evidence


def test_current_roster_requires_complete_pagination_unique_identity_and_cutoff(tmp_path):
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados?itens=100"
    deputy = {"id": 1, "idLegislatura": 57}
    document = {"dados": [deputy], "links": []}
    evidence = archive_page(tmp_path, document, url)
    assert load_dated_roster(tmp_path, date(2026, 10, 29))[2] == date(2026, 10, 29)
    with pytest.raises(ValueError, match="AFTER_CUTOFF"):
        load_dated_roster(tmp_path, date(2026, 10, 28))
    (tmp_path / (evidence["sha256"] + ".json")).write_text("{}")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        load_dated_roster(tmp_path, date(2026, 10, 29))
    archive_page(tmp_path, {"dados": [deputy, deputy]}, url)
    with pytest.raises(ValueError, match="DUPLICATE"):
        load_dated_roster(tmp_path, date(2026, 10, 29))
    archive_page(tmp_path, {**document, "links": [{"rel": "next", "href": url + "&pagina=2"}]}, url)
    with pytest.raises(ValueError, match="INCOHERENT"):
        load_dated_roster(tmp_path, date(2026, 10, 29))


def test_intra_year_source_events_are_deduplicated_and_cutoff_limited():
    event = {"dataHora": "2026-04-01T10:00", "descricaoStatus": "Alteração de partido"}
    rows = [{"official_deputy_id": "1", "events": [event, event,
             dict(event, dataHora="2026-11-01T10:00")]}]
    assert dated_chamber_changes(rows, 2026, "2026-10-29") == [
        {"date": "2026-04-01", "affiliation": 1}]


def test_documented_vacancy_is_separate_from_unobserved_exercise_and_keeps_513_threshold():
    data = chamber({"PL": 296, "PT": 216})
    data["documented_vacancies"] = [{"uf": "ES"}]
    summary = chamber_orientation_summary(data, 2020)
    assert summary["documented_vacant_seats"] == 1
    assert summary["unobserved_seats"] == 0
    assert summary["majority_threshold"] == 257
    data["documented_vacancies"] = None
    assert chamber_orientation_summary(data, 2020)["unobserved_seats"] == 1


def test_duplicate_source_identity_is_rejected_even_with_513_or_fewer_people():
    from service.political_dashboard_dataset.camara_full_history import (
        historical_universe_partition,
    )

    with pytest.raises(ValueError, match="DUPLICATE_PROVIDER"):
        historical_universe_partition([{"source_person_id": "1"}] * 2,
                                      2020, "BR", 2, 2, "a" * 64)
