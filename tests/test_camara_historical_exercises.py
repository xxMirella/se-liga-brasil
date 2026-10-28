from crawlers.camara.historical_exercises import documented_year_end_status

BOUNDS = {54: {"dataInicio": "2011-02-01", "dataFim": "2015-01-31"}}


def event(date, status="Exercício", political_party="DEM"):
    return {
        "idLegislatura": 54,
        "dataHora": date,
        "situacao": status,
        "siglaPartido": political_party,
        "siglaUf": "SP",
    }


def test_historical_placeholder_and_current_party_are_not_backfilled():
    rows = [event("2011-02-01T00:00"), event("2023-02-01T00:00", None, "UNIÃO")]
    assert documented_year_end_status(rows, BOUNDS, 2012)["siglaPartido"] == "DEM"
    assert documented_year_end_status(rows, BOUNDS, 2020) is None


def test_license_and_conflicting_same_time_status_remove_unproven_seat():
    active = event("2011-02-01T00:00")
    licensed = event("2012-10-01T00:00", "Licença")
    assert documented_year_end_status([active, licensed], BOUNDS, 2012) is None
    conflict = event("2011-02-01T00:00", "Licença")
    assert documented_year_end_status([active, conflict], BOUNDS, 2011) is None


def test_party_change_uses_dated_status_and_return_from_license():
    rows = [
        event("2011-02-01T00:00"),
        event("2012-01-01T00:00", "Licença"),
        event("2013-01-01T00:00", political_party="ABC"),
    ]
    assert documented_year_end_status(rows, BOUNDS, 2011)["siglaPartido"] == "DEM"
    assert documented_year_end_status(rows, BOUNDS, 2012) is None
    assert documented_year_end_status(rows, BOUNDS, 2013)["siglaPartido"] == "ABC"


def test_historical_aggregate_keeps_partial_cohort_and_dated_party_namespace():
    from service.political_dashboard_dataset.camara_history import (
        current_cohort_historical_partitions,
    )

    rows = [
        {
            "official_deputy_id": "1",
            "events": [
                {
                    **event("2011-02-01T00:00"),
                    "nome": "Pessoa",
                    "uriPartido": "https://official/DEM",
                }
            ],
            "evidence": [{"fetched_at": "2026-10-23T00:00:00+00:00"}],
        }
    ]
    identities = {"1": {"person_id": "person-1", "source_record_id": "record-1"}}
    partitions = current_cohort_historical_partitions(rows, BOUNDS, identities, 2012)
    national = next(row for row in partitions if row["territory_code"] == "BR")
    assert national["total"] == 1
    assert national["coverage"] == "observed_partial"
    assert national["annual_cohort"] == "current_roster_only_not_all_historical_deputies"
    assert national["political_parties"][0]["political_party_code"] == "camara:https://official/DEM"
    rows[0]["evidence"][0]["fetched_at"] = "2012-06-01T00:00:00+00:00"
    assert current_cohort_historical_partitions(rows, BOUNDS, identities, 2012) == []


def test_history_replay_rejects_prepared_events_that_differ_from_official_archive(tmp_path):
    import json
    from hashlib import sha256

    import pytest

    from crawlers.camara.history_archives import read_verified_history

    content = json.dumps({"dados": [{"id": 1, "situacao": "Licença"}]}).encode()
    digest = sha256(content).hexdigest()
    (tmp_path / "archives").mkdir()
    (tmp_path / "camara-history").mkdir()
    (tmp_path / "archives" / f"{digest}.json").write_bytes(content)
    prepared = {
        "official_deputy_id": "1",
        "events": [{"id": 1, "situacao": "Exercício"}],
        "evidence": [{"sha256": digest}],
    }
    (tmp_path / "camara-history" / "1.json").write_text(json.dumps(prepared))
    with pytest.raises(ValueError, match="DIFFERS_FROM_ARCHIVE"):
        read_verified_history(tmp_path, "1")


def test_historical_state_partition_does_not_copy_other_state_evidence():
    from service.political_dashboard_dataset.camara_history import (
        current_cohort_historical_partitions,
    )

    histories, identities = [], {}
    for identifier, uf in [("1", "SP"), ("2", "RJ")]:
        identities[identifier] = {"person_id": identifier, "source_record_id": identifier}
        histories.append(
            {
                "official_deputy_id": identifier,
                "events": [{**event("2011-02-01T00:00"), "nome": uf, "siglaUf": uf}],
                "evidence": [
                    {"url": f"https://official/{uf}", "fetched_at": "2026-10-23T00:00:00+00:00"}
                ],
            }
        )
    partitions = current_cohort_historical_partitions(histories, BOUNDS, identities, 2012)
    national = next(row for row in partitions if row["territory_code"] == "BR")
    state = next(row for row in partitions if row["territory_code"] == "SP")
    assert len(national["evidence"]) == 2
    assert [row["url"] for row in state["evidence"]] == ["https://official/SP"]
