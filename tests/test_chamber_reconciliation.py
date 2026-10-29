"""Historical reconciliation requires independent exercise and substitution evidence."""

from datetime import date

import pytest

from crawlers.camara.legacy_reconciliation import corroborated_historical_member
from service.political_dashboard.camara_orientation import chamber_orientation_summary
from service.political_dashboard_dataset.chamber_reconciliation import (
    corroborated_vacancy,
    reconciliation_by_uf,
)


def event(identifier="1", status="CONVOCADO", when="2013-03-01T00:00", party="PT"):
    return {"id": int(identifier), "idLegislatura": 54, "dataHora": when,
            "situacao": status, "siglaUf": "PA", "siglaPartido": party,
            "descricaoStatus": "Entrada - Posse de Suplente"}


def evidence_fixture():
    bounds = {54: {"dataInicio": "2011-02-01", "dataFim": "2015-01-31"}}
    period = {"starts_on": date(2013, 3, 1), "ends_on": date(2015, 1, 31), "uf": "PA",
              "previous_source_person_id": "2"}
    records = {("1", 54): {"periods": [period], "evidence": {"sha256": "x"}}}
    return bounds, period, records


def test_legacy_proves_exercise_when_rest_only_records_administrative_summons():
    bounds, period, records = evidence_fixture()
    history = {"official_deputy_id": "1", "events": [event()]}
    assert corroborated_historical_member(history, records, bounds, 2013)[1] == period
    period["ends_on"] = date(2013, 12, 31)
    assert corroborated_historical_member(history, records, bounds, 2013) is None


def test_legacy_does_not_override_party_conflict_or_departure():
    bounds, _, records = evidence_fixture()
    history = {"official_deputy_id": "1", "events": [event(), event(party="PSDB")]}
    assert corroborated_historical_member(history, records, bounds, 2013) is None
    history["events"] = [event(status="Licença")]
    assert corroborated_historical_member(history, records, bounds, 2013) is None


def test_official_substitution_link_and_later_possession_are_both_required_for_vacancy():
    bounds, period, records = evidence_fixture()
    period["starts_on"] = date(2014, 1, 2)
    indexed = {"1": {"events": [event(status="Exercício", when="2014-01-02T12:00")]},
               "2": {"events": [event("2", "VACANCIA", "2013-12-31T00:00")]}}
    record = records[("1", 54)]
    result = corroborated_vacancy(indexed, "2", "1", 54, bounds, period, record,
                                  date(2013, 12, 31))
    assert result["departed_source_person_id"] == "2"
    indexed["2"]["events"][0]["situacao"] = "Licença"
    assert corroborated_vacancy(indexed, "2", "1", 54, bounds, period, record,
                                date(2013, 12, 31)) is None


def test_uf_overcount_cannot_hide_behind_national_deficit():
    with pytest.raises(ValueError, match="UF_CAPACITY"):
        reconciliation_by_uf([{"uf": "PA"}] * 18, [], {"PA": 17, "SP": 70})


def test_historical_policy_never_retrojects_2018_survey_into_2010():
    composition = {"institution_code": "camara", "territory_code": "BR",
                   "expected_seats": 513, "orientation_policy_version": "camara_2010_2019.v1",
                   "total": 513, "political_parties": [{"abbreviation": "PT", "count": 513}]}
    summary = chamber_orientation_summary(composition, 2010)
    assert summary["classified_people"] == 0
    assert summary["absolute_majority"] is None
    assert summary["reference_year"] is None
    assert summary["sensitivity"] == {}
    assert chamber_orientation_summary(composition, 2018)["absolute_majority"] == "left"


def test_legacy_source_hash_and_provider_identity_are_verified(tmp_path):
    import hashlib

    from crawlers.camara.legacy_reconciliation import verified_legacy_record

    raw = (b"<Deputados><Deputado><ideCadastro>1</ideCadastro>"
           b"<numLegislatura>54</numLegislatura></Deputado></Deputados>")
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / (digest + ".xml")).write_bytes(raw)
    evidence = {"url": "https://www.camara.leg.br/SitCamaraWS/Deputados.asmx/"
                       "ObterDetalhesDeputado?ideCadastro=2&numLegislatura=54",
                "sha256": digest, "fetched_at": "2026-10-29T18:00:00+00:00"}
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        verified_legacy_record(tmp_path, evidence)
    evidence["url"] = evidence["url"].replace("ideCadastro=2", "ideCadastro=1")
    assert verified_legacy_record(tmp_path, evidence)[0] == ("1", 54)
    (tmp_path / (digest + ".xml")).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        verified_legacy_record(tmp_path, evidence)


def test_approved_nominal_conflict_matches_exact_rest_signature():
    from crawlers.camara.legacy_reconciliation import corroboratable_rest_group

    row = event(status="Licença")
    record = {"reviewed_rest_conflicts": [{"year": 2013, "rest_status": "Licença",
               "rest_recorded_at": row["dataHora"], "political_party": "PT", "uf": "PA"}]}
    assert corroboratable_rest_group(record, [row], 2013)
    assert not corroboratable_rest_group(record, [dict(row, siglaPartido="PSDB")], 2013)
    assert not corroboratable_rest_group(record, [row], 2014)


def test_administrative_summons_does_not_become_intra_year_entry():
    from service.political_dashboard_dataset.chamber_changes import dated_chamber_changes

    history = {"official_deputy_id": "1", "events": [event()]}
    assert dated_chamber_changes([history], 2013, "2013-12-31") == []
    history["events"][0]["situacao"] = "Exercício"
    assert dated_chamber_changes([history], 2013, "2013-12-31") == [
        {"date": "2013-03-01", "entry": 1}]


def test_documented_name_alignment_is_explicit_dated_and_never_inherits_mergers():
    from service.political_dashboard.camara_orientation import chamber_orientation

    assert chamber_orientation({"abbreviation": "PL"}, 2019)["category"] == "undetermined"
    aligned = chamber_orientation({"abbreviation": "PL"}, 2019, identity_alignment=True)
    assert aligned["reference_political_party"] == "PR"
    assert aligned["identity_alignment"]["effective_on"] == "2019-05-07"
    assert aligned["category"] == "right"
    assert chamber_orientation({"abbreviation": "PATRI"}, 2018,
                               identity_alignment=True)["category"] == "right"
    assert chamber_orientation({"abbreviation": "PL"}, 2018,
                               identity_alignment=True)["category"] == "undetermined"
    assert chamber_orientation({"abbreviation": "PL"}, 2020,
                               identity_alignment=True)["category"] == "undetermined"
    assert chamber_orientation({"abbreviation": "PRD"}, 2019,
                               identity_alignment=True)["category"] == "undetermined"



def test_pre_possession_profile_change_never_establishes_exercise():
    from crawlers.camara.historical_exercises import documented_year_end_status

    metadata = event(status="Exercício", when="2013-12-31T13:44")
    metadata["descricaoStatus"] = (
        "Alteração solicitada via Gabinete Digital, em data anterior à posse."
    )
    bounds, _, _ = evidence_fixture()
    assert documented_year_end_status([metadata], bounds, 2013) is None
    entry = event(status="Exercício", when="2014-01-01T13:36")
    assert documented_year_end_status([metadata, entry], bounds, 2013) is None
    assert documented_year_end_status([metadata, entry], bounds, 2014) == entry



def test_open_legacy_period_is_bounded_by_acquisition_date():
    from crawlers.camara.legacy_exercises import legacy_period_covers_day

    period = {"starts_on": date(2025, 1, 1), "ends_on": None}
    assert not legacy_period_covers_day(period, date(2024, 12, 31), date(2026, 10, 29))
    assert legacy_period_covers_day(period, date(2025, 12, 31), date(2026, 10, 29))
    assert not legacy_period_covers_day(period, date(2026, 12, 31), date(2026, 10, 29))
    assert not legacy_period_covers_day(period, date(2025, 12, 31))
