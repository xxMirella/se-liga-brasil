"""person_fact.original_value is NULL exactly when it equals normalized_value (migration 0027)."""

from uuid import uuid4

import psycopg.errors
import pytest
from psycopg.types.json import Jsonb

from database.operations import read_sql_file, strip_transaction_wrapper

MIGRATION = "migrations/0027_person_fact_original_value_null_when_equal.sql"
ROLLBACK = "rollbacks/0027_restore_person_fact_original_value.sql"


@pytest.fixture
def person_and_record(integration_database):
    db = integration_database
    source = db.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('test','Fictício','https://example.org','api') RETURNING id"
    ).fetchone()["id"]
    record = db.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,payload) VALUES(%s,'test','https://example.org',%s,'{}') RETURNING id",
        (source, "a" * 64),
    ).fetchone()["id"]
    person_id = str(uuid4())
    db.execute(
        "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
        "VALUES(%s,%s,'Pessoa Fictícia','Pessoa Fictícia',%s)",
        (person_id, person_id, record),
    )
    return person_id, record


def insert_fact(db, person_id, record, field_name, original, normalized):
    return db.execute(
        "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
        "normalized_value,evidence_kind,review_status,source_record_id) "
        "VALUES(%s,%s,%s,%s,'administrative','verified',%s) RETURNING id",
        (
            person_id,
            field_name,
            None if original is None else Jsonb(original),
            None if normalized is None else Jsonb(normalized),
            record,
        ),
    ).fetchone()["id"]


def stored_original(db, fact_id):
    return db.execute(
        "SELECT original_value FROM se_liga_brasil.person_fact WHERE id=%s", (fact_id,)
    ).fetchone()["original_value"]


def test_equal_values_are_stored_as_null_and_divergent_values_are_kept(
    integration_database, person_and_record
):
    person_id, record = person_and_record
    equal = insert_fact(integration_database, person_id, record, "a", {"k": 1}, {"k": 1})
    divergent = insert_fact(integration_database, person_id, record, "b", {"k": "1"}, {"k": 1})
    missing_normalized = insert_fact(integration_database, person_id, record, "c", {"k": 1}, None)
    assert stored_original(integration_database, equal) is None
    assert stored_original(integration_database, divergent) == {"k": "1"}
    assert stored_original(integration_database, missing_normalized) == {"k": 1}


def test_changing_normalized_value_preserves_what_null_used_to_mean(
    integration_database, person_and_record
):
    person_id, record = person_and_record
    fact = insert_fact(integration_database, person_id, record, "a", {"k": 1}, {"k": 1})
    integration_database.execute(
        "UPDATE se_liga_brasil.person_fact SET normalized_value=%s WHERE id=%s",
        (Jsonb({"k": 2}), fact),
    )
    assert stored_original(integration_database, fact) == {"k": 1}


def test_status_updates_do_not_touch_original_value(integration_database, person_and_record):
    person_id, record = person_and_record
    fact = insert_fact(integration_database, person_id, record, "a", {"k": 1}, {"k": 1})
    integration_database.execute(
        "UPDATE se_liga_brasil.person_fact SET review_status='conflicting' WHERE id=%s", (fact,)
    )
    assert stored_original(integration_database, fact) is None


def test_null_original_requires_a_normalized_value(integration_database, person_and_record):
    person_id, record = person_and_record
    with (
        pytest.raises(psycopg.errors.CheckViolation),
        integration_database.connection.transaction(),
    ):
        insert_fact(integration_database, person_id, record, "a", None, None)


def test_migration_is_idempotent_and_rollback_restores_every_original_value(
    integration_database, person_and_record
):
    person_id, record = person_and_record
    equal = insert_fact(integration_database, person_id, record, "a", {"k": 1}, {"k": 1})
    divergent = insert_fact(integration_database, person_id, record, "b", {"k": "1"}, {"k": 1})
    for _ in range(2):
        integration_database.execute(strip_transaction_wrapper(read_sql_file(MIGRATION)))
    assert stored_original(integration_database, equal) is None
    assert stored_original(integration_database, divergent) == {"k": "1"}
    for _ in range(2):
        integration_database.execute(strip_transaction_wrapper(read_sql_file(ROLLBACK)))
    assert stored_original(integration_database, equal) == {"k": 1}
    assert stored_original(integration_database, divergent) == {"k": "1"}
    integration_database.execute(strip_transaction_wrapper(read_sql_file(MIGRATION)))
    assert stored_original(integration_database, equal) is None
