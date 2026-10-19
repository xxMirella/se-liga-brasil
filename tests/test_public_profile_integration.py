"""Real SQL in a disposable schema; the fixture rolls back every fictional fact."""

from datetime import date
from uuid import uuid4

import pytest

from database.public_profile import PublicProfileRepository
from service.public_profile import VoteQuery
from service.public_profile.pagination import decode_vote_cursor, encode_vote_cursor
from service.public_profile.votes import serialize_vote, summarize_coverage


def create_public_read_fixture(connection):
    source_id = connection.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('fixture','Fixture','https://example.invalid','api') RETURNING id"
    ).fetchone()["id"]
    record_id = connection.execute(
        "INSERT INTO se_liga_brasil.source_record"
        "(source_id,external_key,source_url,content_sha256,payload) "
        "VALUES(%s,'fixture','https://example.invalid',repeat('a',64),'{}') RETURNING id",
        (source_id,),
    ).fetchone()["id"]
    person_id, other_id = str(uuid4()), str(uuid4())
    for identifier in (person_id, other_id):
        connection.execute(
            "INSERT INTO se_liga_brasil.person"
            "(id,slug,civil_name,display_name,primary_record_id) "
            "VALUES(%s,%s,'Identificação privada fictícia','Perfil demonstrativo',%s)",
            (identifier, identifier, record_id),
        )
    institution_ids = []
    for code in ("senado", "fixture_other"):
        institution_ids.append(
            connection.execute(
                "INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url) "
                "VALUES(%s,'Órgão demonstrativo','federal','BR','https://example.invalid') "
                "RETURNING id",
                (code,),
            ).fetchone()["id"]
        )
    term_id = connection.execute(
        "INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,"
        "represented_uf,legislature_key,official_term_key,term_start,term_end,source_record_id) "
        "VALUES(%s,%s,'senator','SP','fixture','fixture','2026-01-01','2027-01-01',%s) "
        "RETURNING id",
        (person_id, institution_ids[0], record_id),
    ).fetchone()["id"]
    exercise_id = connection.execute(
        "INSERT INTO se_liga_brasil.office_exercise"
        "(term_id,starts_on,ends_before,capacity,source_record_id) "
        "VALUES(%s,'2026-10-14','2026-10-15','holder',%s) RETURNING id",
        (term_id, record_id),
    ).fetchone()["id"]
    return person_id, other_id, record_id, institution_ids, exercise_id


def insert_public_read_votes(connection, person_id, other_id, record_id, institution_ids):
    identifiers = []
    for institution_id, days in zip(institution_ids, ([13, 14, 14, 15], [14]), strict=True):
        proposition_id = connection.execute(
            "INSERT INTO se_liga_brasil.proposition"
            "(institution_id,official_key,kind,number,year,title,current_status,"
            "status_as_of,source_record_id) "
            "VALUES(%s,'fixture','PL','1',2026,'Texto demonstrativo','in_progress',now(),%s) "
            "RETURNING id",
            (institution_id, record_id),
        ).fetchone()["id"]
        for sequence, day in enumerate(days):
            voting_id = connection.execute(
                "INSERT INTO se_liga_brasil.voting"
                "(proposition_id,institution_id,official_key,held_on,date_precision,subject,"
                "method,result,source_record_id,nominal_availability) "
                "VALUES(%s,%s,%s,%s,'day','Texto principal','roll_call','approved',%s,'available') "
                "RETURNING id",
                (proposition_id, institution_id, str(sequence), date(2026, 10, day), record_id),
            ).fetchone()["id"]
            for identifier, choice in ((person_id, "no"), (other_id, "yes")):
                connection.execute(
                    "INSERT INTO se_liga_brasil.person_vote"
                    "(voting_id,person_id,choice,participation_status,source_record_id) "
                    "VALUES(%s,%s,%s,'voted',%s)",
                    (voting_id, identifier, choice, record_id),
                )
            identifiers.append(voting_id)
    return identifiers


def insert_public_read_coverage(connection, person_id):
    for channel in ("plenary", "committee"):
        connection.execute(
            "INSERT INTO se_liga_brasil.person_career_coverage_receipt"
            "(person_id,institution,domain,source,partition_key,starts_on,ends_before,checked_on,"
            "identity_verified,enumeration_complete,source_period_complete,artifact_verified,"
            "scope_verified,artifact_sha256,parser_version,acquisition_status) "
            "VALUES(%s,'senado','votes','senado',%s,'2026-10-01','2026-11-01','2026-10-17',"
            "true,true,true,true,true,repeat('a',64),'test','available')",
            (person_id, channel + "/2026-10"),
        )


@pytest.mark.integration
def test_real_public_read_joins_exercise_pagination_and_coverage(integration_database):
    connection = integration_database
    person_id, other_id, record_id, institutions, exercise_id = create_public_read_fixture(
        connection
    )
    insert_public_read_votes(connection, person_id, other_id, record_id, institutions)
    insert_public_read_coverage(connection, person_id)
    repository = PublicProfileRepository(connection)
    query = VoteQuery(
        person_id,
        date(2026, 10, 1),
        date(2026, 10, 31),
        office_kind="senator",
        exercise_id=exercise_id,
        limit=1,
    )
    assert repository.fetch_person(person_id)["display_name"] == "Perfil demonstrativo"
    exercises = repository.fetch_exercises(query)
    assert len(exercises) == 1 and exercises[0]["exercise_id"] == exercise_id
    first_rows = repository.fetch_votes(query, None)
    assert len(first_rows) == 2
    assert all(row["held_on"] == date(2026, 10, 14) for row in first_rows)
    assert all(row["institution_code"] == "senado" for row in first_rows)
    first = first_rows[0]
    cursor = encode_vote_cursor(query, first["held_on"], first["voting_id"])
    next_query = VoteQuery(
        person_id, query.start_on, query.end_on, "senator", exercise_id, cursor, 1
    )
    second_rows = repository.fetch_votes(next_query, decode_vote_cursor(next_query))
    assert len(second_rows) == 1 and second_rows[0]["voting_id"] != first["voting_id"]
    item = serialize_vote(first)
    assert item["individual"]["choice"] == "no" and item["collective_result"] == "approved"
    assert item["month"] == "2026-10"
    assert not {"civil_name", "source_record_id", "person_id", "payload"}.intersection(item)
    receipts = repository.fetch_vote_coverage(query)
    coverage = summarize_coverage(receipts, exercises, False, True)
    assert {row["channel"] for row in coverage["intervals"]} == {"plenary", "committee"}
    assert coverage["requested_period_state"] == "not_certified"
    wrong = VoteQuery(person_id, query.start_on, query.end_on, "councillor")
    assert repository.fetch_votes(wrong, None) == []
    unfiltered = VoteQuery(person_id, query.start_on, query.end_on)
    assert len(repository.fetch_votes(unfiltered, None)) == 5
    assert repository.fetch_person(str(uuid4())) is None
