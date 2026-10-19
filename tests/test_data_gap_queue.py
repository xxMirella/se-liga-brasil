from uuid import uuid4

import pytest

from database.data_gaps import (
    claim_data_gaps,
    persist_data_gaps,
    postpone_source,
    release_data_gaps,
)
from service.orchestration.data_collection import group_source_requests


@pytest.fixture
def gap_person(integration_database):
    db = integration_database
    source = db.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('tse','Teste','https://example.org','download') RETURNING id"
    ).fetchone()
    record = db.execute(
        """INSERT INTO se_liga_brasil.source_record(
          source_id,external_key,source_url,content_sha256,payload)
          VALUES(%s,'test','https://example.org',%s,'{}') RETURNING id""",
        (source["id"], "a" * 64),
    ).fetchone()
    person_id = str(uuid4())
    db.execute(
        "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
        "VALUES(%s,%s,'Pessoa Fictícia','Pessoa Fictícia',%s)",
        (person_id, person_id, record["id"]),
    )
    return person_id


def report(person_id, state="missing"):
    return {
        "people": [
            {"person_id": person_id, "fields": {"birth_date": state, "current_salary": state}}
        ]
    }


@pytest.mark.integration
def test_gap_queue_is_idempotent_and_marks_resolution(integration_database, gap_person):
    db = integration_database
    for _ in range(2):
        persist_data_gaps(db, report(gap_person))
    assert (
        db.execute("SELECT count(*) AS total FROM se_liga_brasil.person_data_gap").fetchone()[
            "total"
        ]
        == 2
    )
    db.execute("UPDATE se_liga_brasil.person_data_gap SET assigned_source='tse'")
    worker = str(uuid4())
    assert len(claim_data_gaps(db, worker)) == 2
    assert not claim_data_gaps(db, str(uuid4()))
    persist_data_gaps(db, report(gap_person, "present"))
    rows = db.execute(
        "SELECT status,attempts,claimed_by FROM se_liga_brasil.person_data_gap"
    ).fetchall()
    assert all(
        row["status"] == "resolved" and row["attempts"] == 1 and row["claimed_by"] is None
        for row in rows
    )


@pytest.mark.integration
def test_reassessment_does_not_reset_source_cooldown(integration_database, gap_person):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    db.execute("UPDATE se_liga_brasil.person_data_gap SET assigned_source='tse'")
    worker = str(uuid4())
    claim_data_gaps(db, worker)
    postpone_source(db, "tse", 172800, "HTTP_ERROR")
    release_data_gaps(db, worker)
    new_report = report(gap_person)
    new_report["people"][0]["fields"]["education_level"] = "missing"
    persist_data_gaps(db, new_report)
    db.execute("UPDATE se_liga_brasil.person_data_gap SET assigned_source='tse'")
    assert not claim_data_gaps(db, str(uuid4()))
    assert db.execute(
        "SELECT bool_and(next_attempt_at>now()+interval '25 hours') AS delayed "
        "FROM se_liga_brasil.person_data_gap WHERE field_name<>'education_level'"
    ).fetchone()["delayed"]


def test_many_missing_fields_become_one_person_request_per_source():
    tasks = [
        {"assigned_source": "camara", "person_id": "p", "field_name": field}
        for field in ("current_salary", "current_political_party", "current_public_office")
    ]
    result = group_source_requests(tasks)
    assert len(result) == 1 and len(result["camara"]) == 1
    assert len(result["camara"]["p"]) == 3


@pytest.mark.integration
def test_cleanup_removes_only_confirmed_gaps(integration_database, gap_person):
    from service.maintenance.data_gap_cleanup import purge_processed_gaps

    db = integration_database
    persist_data_gaps(db, report(gap_person))
    updated = report(gap_person)
    updated["people"][0]["fields"]["birth_date"] = "present"
    persist_data_gaps(db, updated)
    assert purge_processed_gaps(db, batch_size=1)["deleted_processed_gaps"] == 1
    remaining = db.execute(
        "SELECT field_name,is_processed,processed_at FROM se_liga_brasil.person_data_gap"
    ).fetchall()
    assert len(remaining) == 1
    assert remaining[0]["field_name"] == "current_salary"
    assert remaining[0]["is_processed"] is False
    assert remaining[0]["processed_at"] is None
    assert purge_processed_gaps(db)["deleted_processed_gaps"] == 0
    assert (
        db.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.person WHERE id=%s", (gap_person,)
        ).fetchone()["total"]
        == 1
    )


@pytest.mark.integration
def test_routes_use_state_and_reassign_existing_wrong_source(integration_database, gap_person):
    from database.data_gaps import route_data_gaps

    db = integration_database
    persist_data_gaps(db, report(gap_person))
    source_id = db.execute("SELECT id FROM se_liga_brasil.source WHERE code='tse'").fetchone()["id"]
    record_id = db.execute(
        "SELECT primary_record_id FROM se_liga_brasil.person WHERE id=%s", (gap_person,)
    ).fetchone()["primary_record_id"]
    db.execute(
        "INSERT INTO se_liga_brasil.electoral_candidacy(source_id,external_key,person_id,"
        "election_year,election_id,candidate_sequence,election_round,represented_uf,"
        "office_code,office_name,source_record_id,source_generated_at) "
        "VALUES(%s,'test',%s,2026,'1','123',1,'SP','7','Teste',%s,now())",
        (source_id, gap_person, record_id),
    )
    for uf, office, expected in (("SP", "7", "alesp"), ("RJ", "7", "alerj"), ("RJ", "5", "senado")):
        db.execute(
            "UPDATE se_liga_brasil.electoral_candidacy SET represented_uf=%s,office_code=%s",
            (uf, office),
        )
        route_data_gaps(db)
        routes = {
            row["field_name"]: row["assigned_source"]
            for row in db.execute(
                "SELECT field_name,assigned_source FROM se_liga_brasil.person_data_gap"
            ).fetchall()
        }
        assert routes == {"birth_date": "tse", "current_salary": expected}


@pytest.mark.integration
def test_unmatched_institution_blocks_repeats_without_claiming_no_office(
    integration_database,
    gap_person,
):
    from database.data_gaps import defer_unmatched_institutional_people, route_data_gaps
    from service.maintenance.data_gap_cleanup import purge_processed_gaps

    db = integration_database
    missing = {
        "people": [
            {
                "person_id": gap_person,
                "fields": {
                    "current_political_party": "missing",
                    "current_public_office": "missing",
                    "current_salary": "missing",
                },
            }
        ]
    }
    persist_data_gaps(db, missing)
    db.execute("UPDATE se_liga_brasil.person_data_gap SET assigned_source='camara'")
    worker = str(uuid4())
    assert len(claim_data_gaps(db, worker)) == 3
    defer_unmatched_institutional_people(db, worker, "camara", [gap_person])
    rows = {
        row["field_name"]: row
        for row in db.execute(
            "SELECT field_name,status,assigned_source,is_processed "
            "FROM se_liga_brasil.person_data_gap"
        ).fetchall()
    }
    assert rows["current_public_office"]["status"] == "blocked"
    assert rows["current_salary"]["status"] == "blocked"
    assert rows["current_political_party"]["assigned_source"] == "tse_filiation"
    assert all(not row["is_processed"] for row in rows.values())
    assert purge_processed_gaps(db)["deleted_processed_gaps"] == 0
    route_data_gaps(db)
    assert (
        db.execute(
            "SELECT assigned_source FROM se_liga_brasil.person_data_gap "
            "WHERE field_name='current_political_party'"
        ).fetchone()["assigned_source"]
        == "tse_filiation"
    )
    assert (
        db.execute(
            "SELECT has_current_public_office FROM se_liga_brasil.person WHERE id=%s", (gap_person,)
        ).fetchone()["has_current_public_office"]
        is None
    )


@pytest.mark.integration
def test_local_alesp_field_can_run_while_remote_salary_is_delayed(integration_database, gap_person):
    db = integration_database
    db.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('alesp','Teste','https://example.org','download')"
    )
    persist_data_gaps(
        db,
        {
            "people": [
                {
                    "person_id": gap_person,
                    "fields": {
                        "current_salary": "missing",
                        "political_activity": "missing",
                    },
                }
            ]
        },
    )
    db.execute("UPDATE se_liga_brasil.person_data_gap SET assigned_source='alesp'")
    postpone_source(db, "alesp", 172800, "HTTP_ERROR")
    db.execute("UPDATE se_liga_brasil.person_data_gap SET next_attempt_at=now()")
    local = claim_data_gaps(db, str(uuid4()), field_names=["political_activity"])
    assert len(local) == 1 and local[0]["field_name"] == "political_activity"
    assert not claim_data_gaps(db, str(uuid4()), field_names=["current_salary"])


@pytest.mark.integration
def test_future_candidacy_does_not_hide_a_senate_discovery_hint(integration_database, gap_person):
    from database.data_gaps import route_data_gaps

    db = integration_database
    persist_data_gaps(db, report(gap_person))
    primary = db.execute(
        "SELECT primary_record_id FROM se_liga_brasil.person WHERE id=%s", (gap_person,)
    ).fetchone()["primary_record_id"]
    source = db.execute("SELECT id FROM se_liga_brasil.source WHERE code='tse'").fetchone()["id"]
    for year, code in ((2018, "5"), (2026, "7")):
        db.execute(
            "INSERT INTO se_liga_brasil.electoral_candidacy(source_id,external_key,person_id,"
            "election_year,election_id,candidate_sequence,election_round,represented_uf,"
            "office_code,office_name,election_result,source_record_id,source_generated_at) "
            "VALUES(%s,%s,%s,%s,'1','123',1,'SP',%s,'Teste','Eleito',%s,now())",
            (source, str(year), gap_person, year, code, primary),
        )
    route_data_gaps(db)
    assert (
        db.execute(
            "SELECT assigned_source FROM se_liga_brasil.person_data_gap "
            "WHERE field_name='current_salary'"
        ).fetchone()["assigned_source"]
        == "senado"
    )
    assert (
        db.execute(
            "SELECT has_current_public_office FROM se_liga_brasil.person WHERE id=%s", (gap_person,)
        ).fetchone()["has_current_public_office"]
        is None
    )
