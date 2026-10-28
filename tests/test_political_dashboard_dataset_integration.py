"""Exercise annual publication and web reads only in a rollback-only isolated schema."""

from contextlib import nullcontext
from datetime import date

import pytest

from database.operations import read_sql_file
from database.political_dashboard_analytical import AnnualDashboardRepository
from service.political_dashboard_dataset.executive import build_annual_executive_partitions


@pytest.mark.integration
def test_yearly_publication_preserves_other_years_and_year_only_history(
    integration_database,
    monkeypatch,
):
    integration_database.execute(read_sql_file("political_dashboard_annual.sql"))
    monkeypatch.setattr(AnnualDashboardRepository, "read_snapshot", lambda _: nullcontext())
    repository = AnnualDashboardRepository(integration_database)
    source = [
        {
            "territory_code": "BR",
            "institution_code": "presidency",
            "name": "Pessoa Fictícia",
            "year_start": 1889,
            "year_end": 1890,
            "date_precision": "year",
        }
    ]
    first = build_annual_executive_partitions(source, 1889, date(2026, 10, 23))
    second = build_annual_executive_partitions(source, 1890, date(2026, 10, 23))
    repository.activate_partitions(first + second)
    old_generation = repository.fetch_generation_hashes(1889)
    second[0]["segments"][0]["name"] = "Outra Pessoa Fictícia"
    second[0]["national_observations"] = [
        {
            "name": "Observação Fictícia",
            "political_party": "ABC",
            "political_party_status": "verified_official_inauguration_observation",
            "source_observed_on": "1890-01-01",
            "evidence": [{"url": "https://example.test"}],
        }
    ]
    repository.activate_partitions(second)
    assert repository.fetch_generation_hashes(1889) == old_generation
    assert repository.fetch_partitions(1889, ["SP"]) == []
    assert repository.fetch_partitions(1890, ["BR"])[0]["payload"]["current"] is None
    assert [row["total"] for row in repository.fetch_history(["BR"], 1890)] == [1, 1]
    snapshot = repository.fetch_annual_snapshot(1890, ["BR"])
    compact = snapshot["history"][0]["composition"]
    assert compact["segments"][0]["name"] == "Pessoa Fictícia"
    assert "evidence" not in compact["segments"][0]
    assert "members" not in compact
    later = snapshot["history"][1]["composition"]["national_observations"][0]
    assert later["political_party"] == "ABC"
    assert later["source_observed_on"] == "1890-01-01"
    assert "evidence" not in later
    assert len(snapshot["partitions"]) == 1
    assert [row["year"] for row in snapshot["history"]] == [1889, 1890]


@pytest.mark.integration
def test_failed_annual_generation_does_not_replace_previous_activated_dataset(
    integration_database,
    monkeypatch,
):
    integration_database.execute(read_sql_file("political_dashboard_annual.sql"))
    monkeypatch.setattr(AnnualDashboardRepository, "read_snapshot", lambda _: nullcontext())
    repository = AnnualDashboardRepository(integration_database)
    original = {"year": 2026, "territory_code": "BR", "institution_code": "presidency"}
    repository.activate_partitions([original])
    with pytest.raises(ValueError, match="PAYLOAD_BUDGET"):
        repository.activate_partitions(
            [{**original, "changed": True}, {**original, "oversized": "x" * 262144}]
        )
    assert repository.fetch_partitions(2026, ["BR"])[0]["payload"] == original


@pytest.mark.integration
def test_invalid_df_state_projection_is_removed_only_after_correct_district_exists(
    integration_database,
    monkeypatch,
):
    integration_database.execute(read_sql_file("political_dashboard_annual.sql"))
    repository = AnnualDashboardRepository(integration_database)
    monkeypatch.setattr(AnnualDashboardRepository, "read_snapshot", lambda _: nullcontext())
    invalid = {"year": 2026, "territory_code": "DF", "institution_code": "state_government"}
    other_state = {**invalid, "territory_code": "SP"}
    repository.activate_partitions([invalid, other_state])
    assert repository.remove_replaced_invalid_district_government() == 0
    valid = {**invalid, "institution_code": "district_government"}
    repository.activate_partitions([valid])
    assert repository.remove_replaced_invalid_district_government() == 1
    assert repository.fetch_partitions(2026, ["DF"])[0]["payload"] == valid
    assert repository.fetch_partitions(2026, ["SP"])[0]["payload"] == other_state


@pytest.mark.integration
def test_presidential_party_periods_are_compact_and_tolerate_explicit_json_null(
    integration_database,
    monkeypatch,
):
    integration_database.execute(read_sql_file("political_dashboard_annual.sql"))
    monkeypatch.setattr(AnnualDashboardRepository, "read_snapshot", lambda _: nullcontext())
    repository = AnnualDashboardRepository(integration_database)
    period = {
        "political_party": "TESTE",
        "political_party_status": "verified_government_classification",
        "political_party_context": "original_research_government_classification",
        "date_precision": "year",
        "starts_on": "2001-01-01",
        "ends_before": "2002-01-01",
        "evidence": [{"url": "https://example.test/source", "sha256": "a" * 64}],
    }
    person = {"name": "Pessoa Fictícia", "political_party_periods": [period]}
    context = {
        "date": "2001-03-24", "title": "Contexto documentado", "organization": "TESTE",
        "relationship": "government_support_organization_not_personal_affiliation",
        "summary": "Apoio não comprova filiação pessoal.",
        "source_url": "https://example.test/context",
        "evidence": [{"sha256": "b" * 64, "large_text": "not in compact response"}],
    }
    partition = {
        "year": 2001,
        "territory_code": "BR",
        "institution_code": "presidency",
        "current": person,
        "segments": [person],
        "government_context_observations": [context],
    }
    repository.activate_partitions([partition])
    compact = repository.fetch_annual_snapshot(2001, ["BR"])["history"][0]["composition"]
    for item in [compact["current"], *compact["segments"]]:
        assert item["political_party_periods"][0] == {
            **{key: value for key, value in period.items() if key != "evidence"},
            "source_url": period["evidence"][0]["url"],
        }
    assert compact["government_context_observations"] == [
        {key: value for key, value in context.items() if key != "evidence"}
    ]
    for malformed in [None, {}, "invalid"]:
        partition["current"]["political_party_periods"] = malformed
        partition["government_context_observations"] = malformed
        repository.activate_partitions([partition])
        compact = repository.fetch_annual_snapshot(2001, ["BR"])["history"][0]["composition"]
        assert compact["current"]["political_party_periods"] == []
        assert compact["segments"][0]["political_party_periods"] == []
        assert compact["government_context_observations"] == []


@pytest.mark.integration
def test_new_assembly_source_is_registered_before_cooldown_can_be_persisted(integration_database):
    from database.data_gaps import postpone_source
    from database.state_assembly_rosters import StateAssemblyRosterRepository
    from service.ingestion.contracts import SourceDescriptor

    source = SourceDescriptor("test_assembly_source", "Fonte Fictícia", "https://example.test")
    repository = StateAssemblyRosterRepository(integration_database)
    repository.ensure_official_source(source)
    repository.ensure_official_source(source)
    postpone_source(integration_database, source.code, 3600, "HTTP_ERROR", 503)
    policy = integration_database.execute(
        "SELECT last_http_status,cooldown_until>now() AS deferred "
        "FROM se_liga_brasil.source_request_policy WHERE source_code=%s",
        (source.code,),
    ).fetchone()
    assert policy == {"last_http_status": 503, "deferred": True}


@pytest.mark.integration
def test_imperial_history_and_transition_metadata_survive_compact_read(
    integration_database, monkeypatch,
):
    integration_database.execute(read_sql_file("political_dashboard_annual.sql"))
    monkeypatch.setattr(AnnualDashboardRepository, "read_snapshot", lambda _: nullcontext())
    repository = AnnualDashboardRepository(integration_database)
    repository.activate_partitions([
        {"year": 1826, "territory_code": "BR", "institution_code": "senado", "total": None},
        {"year": 1938, "territory_code": "BR", "institution_code": "senado",
         "institutional_status": "suspended_whole_year",
         "institutional_status_label": "Instituição suspensa"},
        {"year": 2016, "territory_code": "BR", "institution_code": "presidency",
         "segments": [{"name": "Pessoa Fictícia", "person_id": "source:1",
                       "starts_on": "2016-05-12", "ends_before": "2016-08-31",
                       "exercise_capacity": "acting_president", "date_precision": "day",
                       "official_url": "https://www.gov.br/exercicio",
                       "exercise_capacity_evidence": [{"url": "https://www.camara.leg.br/fonte"}],
                       "evidence": [{"large": "must not enter compact history"}]}]},
    ])
    history = repository.fetch_annual_snapshot(2016, ["BR"])["history"]
    assert history[0]["year"] == 1826
    assert history[1]["composition"]["institutional_status"] == "suspended_whole_year"
    record = history[2]["composition"]["segments"][0]
    assert record["person_id"] == "source:1"
    assert record["starts_on"] == "2016-05-12"
    assert record["exercise_capacity"] == "acting_president"
    assert record["source_url"] == "https://www.gov.br/exercicio"
    assert record["exercise_capacity_source_url"] == "https://www.camara.leg.br/fonte"
    assert "evidence" not in record
