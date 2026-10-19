from datetime import date, timedelta
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from database.public_office import refresh_current_public_offices


@pytest.fixture
def office_person(integration_database):
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
    db.execute(
        "INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url) "
        "VALUES('test','Instituição Fictícia','state','SP','https://example.org')"
    )
    return person_id, record


def insert_office_fact(db, person_id, record, field, value):
    db.execute(
        "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
        "normalized_value,evidence_kind,review_status,source_record_id) "
        "VALUES(%s,%s,%s,%s,'administrative','verified',%s)",
        (person_id, field, Jsonb(value), Jsonb(value), record),
    )


def current_status(db, person_id):
    return db.execute(
        "SELECT has_current_public_office,current_public_office_kind,"
        "current_public_office_term_id FROM se_liga_brasil.person WHERE id=%s",
        (person_id,),
    ).fetchone()


@pytest.mark.integration
def test_current_observation_updates_person_without_inventing_exercise_date(
    integration_database,
    office_person,
):
    db = integration_database
    person_id, record = office_person
    refresh_current_public_offices(db)
    assert current_status(db, person_id)["has_current_public_office"] is None
    insert_office_fact(
        db,
        person_id,
        record,
        "current_public_office_observation",
        {
            "inExercise": True,
            "observedOn": date.today().isoformat(),
            "officeKind": "state_deputy",
            "institutionCode": "test",
        },
    )
    refresh_current_public_offices(db)
    status = current_status(db, person_id)
    assert status["has_current_public_office"] is True
    assert status["current_public_office_kind"] == "state_deputy"
    assert status["current_public_office_term_id"] is None
    assert (
        db.execute("SELECT count(*) AS total FROM se_liga_brasil.office_exercise").fetchone()[
            "total"
        ]
        == 0
    )
    refresh_current_public_offices(db)
    assert current_status(db, person_id) == status
    db.execute(
        "UPDATE se_liga_brasil.person_fact SET normalized_value=normalized_value||%s "
        "WHERE field_name='current_public_office_observation'",
        (Jsonb({"exerciseEndExclusive": date.today().isoformat()}),),
    )
    refresh_current_public_offices(db)
    assert current_status(db, person_id)["has_current_public_office"] is None


@pytest.mark.integration
def test_institutional_absence_is_not_global_absence(integration_database, office_person):
    db = integration_database
    person_id, record = office_person
    insert_office_fact(
        db,
        person_id,
        record,
        "current_public_office_observation",
        {
            "inExercise": False,
            "observedOn": date.today().isoformat(),
            "officeKind": "state_deputy",
            "institutionCode": "test",
        },
    )
    refresh_current_public_offices(db)
    assert current_status(db, person_id)["has_current_public_office"] is None
    insert_office_fact(
        db,
        person_id,
        record,
        "public_office_status",
        {
            "hasCurrentPublicOffice": False,
            "scope": "all_public_offices",
            "validFrom": date.today().isoformat(),
            "validUntil": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    refresh_current_public_offices(db)
    assert current_status(db, person_id)["has_current_public_office"] is False
    db.execute(
        "UPDATE se_liga_brasil.person_fact SET normalized_value=normalized_value||%s "
        "WHERE field_name='public_office_status'",
        (Jsonb({"validUntil": date.today().isoformat()}),),
    )
    refresh_current_public_offices(db)
    assert current_status(db, person_id)["has_current_public_office"] is None
