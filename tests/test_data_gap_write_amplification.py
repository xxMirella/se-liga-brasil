"""Gap writes must change a row only when the observable gap state changes."""

from uuid import uuid4

import pytest
from test_data_gap_queue import report

from database.data_gaps import persist_data_gaps, postpone_source
from service.orchestration.data_collection import release_deferred_people

TABLE = "se_liga_brasil.person_data_gap"


@pytest.fixture
def gap_person(integration_database):
    db = integration_database
    source = db.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('tse','Teste','https://example.org','download') RETURNING id"
    ).fetchone()
    record = db.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,payload) VALUES(%s,'test','https://example.org',%s,'{}') RETURNING id",
        (source["id"], "a" * 64),
    ).fetchone()
    person_id = str(uuid4())
    db.execute(
        "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
        "VALUES(%s,%s,'Pessoa Fictícia','Pessoa Fictícia',%s)",
        (person_id, person_id, record["id"]),
    )
    return person_id


class RecordingConnection:
    def __init__(self):
        self.statements = []

    def execute(self, query, parameters=None):
        self.statements.append((query, parameters))

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


def test_persist_stages_only_unsatisfied_fields_and_guards_the_rewrite():
    connection = RecordingConnection()
    person_id = str(uuid4())
    payload = {"people": [{"person_id": person_id, "fields": {"a": "missing", "b": "present"}}]}
    result = persist_data_gaps(connection, payload)
    assert result["open_fields_assessed"] == 1
    sql = "\n".join(query for query, _ in connection.statements)
    assert "IS DISTINCT FROM excluded.quality_state" in sql
    assert "NOT EXISTS" in sql


def test_postpone_source_update_is_guarded_by_effective_change():
    connection = RecordingConnection()
    postpone_source(connection, "tse", 60, "HTTP_ERROR")
    update_sql = connection.statements[-1][0]
    assert "IS DISTINCT FROM %s" in update_sql
    assert "next_attempt_at<now()" in update_sql


def row_versions(db):
    return {
        (row["field_name"]): (row["ctid"], row["last_checked_at"], row["last_assessment_id"])
        for row in db.execute(
            f"SELECT field_name,ctid::text AS ctid,last_checked_at,last_assessment_id FROM {TABLE}"
        ).fetchall()
    }


def age_gap_rows(db):
    db.execute(
        f"UPDATE {TABLE} SET last_checked_at=now()-interval '3 days',"
        "next_attempt_at=now()-interval '1 hour',assigned_source='tse'"
    )


@pytest.mark.integration
def test_reassessment_without_change_does_not_rewrite_rows(integration_database, gap_person):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    age_gap_rows(db)
    before = row_versions(db)
    persist_data_gaps(db, report(gap_person))
    assert row_versions(db) == before


@pytest.mark.integration
def test_changed_quality_state_still_updates_only_that_row(integration_database, gap_person):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    age_gap_rows(db)
    before = row_versions(db)
    changed = report(gap_person)
    changed["people"][0]["fields"]["birth_date"] = "invalid"
    result = persist_data_gaps(db, changed)
    after = row_versions(db)
    assert after["current_salary"] == before["current_salary"]
    assert after["birth_date"][0] != before["birth_date"][0]
    assert after["birth_date"][1] > before["birth_date"][1]
    assert after["birth_date"][2] == uuid_text(result["assessment_id"])
    state = db.execute(f"SELECT quality_state FROM {TABLE} WHERE field_name='birth_date'")
    assert state.fetchone()["quality_state"] == "invalid"


def uuid_text(value):
    from uuid import UUID

    return UUID(value)


@pytest.mark.integration
def test_absent_gap_is_resolved_and_untouched_peer_is_not_rewritten(
    integration_database, gap_person
):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    age_gap_rows(db)
    before = row_versions(db)
    partial = {"people": [{"person_id": gap_person, "fields": {"current_salary": "missing"}}]}
    persist_data_gaps(db, partial)
    after = row_versions(db)
    assert after["current_salary"] == before["current_salary"]
    resolved = db.execute(
        f"SELECT status,quality_state,is_processed,resolved_at FROM {TABLE} "
        "WHERE field_name='birth_date'"
    ).fetchone()
    assert resolved["status"] == "resolved" and resolved["quality_state"] == "resolved"
    assert resolved["is_processed"] and resolved["resolved_at"] is not None


@pytest.mark.integration
def test_resolved_gap_that_reappears_is_requeued(integration_database, gap_person):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    persist_data_gaps(db, report(gap_person, "present"))
    persist_data_gaps(db, report(gap_person))
    rows = db.execute(f"SELECT status,is_processed,resolved_at FROM {TABLE}").fetchall()
    assert len(rows) == 2
    assert all(
        row["status"] == "queued" and not row["is_processed"] and row["resolved_at"] is None
        for row in rows
    )


@pytest.mark.integration
def test_postpone_source_rewrites_only_when_cooldown_or_error_changes(
    integration_database, gap_person
):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    age_gap_rows(db)
    postpone_source(db, "tse", 7200, "HTTP_ERROR")
    first = row_versions(db)
    postpone_source(db, "tse", 7200, "HTTP_ERROR")
    postpone_source(db, "tse", 60, "HTTP_ERROR")
    assert row_versions(db) == first
    postpone_source(db, "tse", 86400, "HTTP_ERROR")
    longer = row_versions(db)
    assert all(longer[name][0] != first[name][0] for name in first)
    postpone_source(db, "tse", 60, "RATE_LIMITED")
    assert all(row_versions(db)[name][0] != longer[name][0] for name in first)
    delays = db.execute(f"SELECT next_attempt_at>now()+interval '23 hours' AS ok FROM {TABLE}")
    assert all(row["ok"] for row in delays.fetchall())


@pytest.mark.integration
def test_release_deferred_people_only_touches_rows_not_yet_due(integration_database, gap_person):
    db = integration_database
    persist_data_gaps(db, report(gap_person))
    age_gap_rows(db)
    db.execute(
        f"UPDATE {TABLE} SET next_attempt_at=now()+interval '2 days' WHERE field_name='birth_date'"
    )
    before = row_versions(db)
    results = {"tse": {"deferred_person_ids": [gap_person]}}
    release_deferred_people(db, results)
    after = row_versions(db)
    assert after["current_salary"] == before["current_salary"]
    assert after["birth_date"][0] != before["birth_date"][0]
    release_deferred_people(db, results)
    assert row_versions(db) == after
    due = db.execute(f"SELECT bool_and(next_attempt_at<=now()) AS due FROM {TABLE}").fetchone()
    assert due["due"]
