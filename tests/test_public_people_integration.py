"""Canonical public SQL runs only in the rollback-only disposable fixture schema."""

from datetime import date

import pytest
from test_public_profile_integration import create_public_read_fixture

from database.public_people import PublicPeopleRepository
from service.public_profile.people import PeopleQuery


@pytest.mark.integration
def test_public_people_sql_filters_aliases_temporal_facts_and_stable_page(integration_database):
    connection = integration_database
    person_id, other_id, record_id, _, _ = create_public_read_fixture(connection)
    repository = PublicPeopleRepository(connection)
    as_of = date(2026, 10, 14)
    page = repository.search_people(PeopleQuery(q="Perfil", limit=1), as_of, None)
    assert len(page) == 2
    following = repository.search_people(
        PeopleQuery(q="Perfil", limit=1),
        as_of,
        (page[0]["display_name"], page[0]["person_id"]),
    )
    assert [row["person_id"] for row in following] == [page[1]["person_id"]]
    matching = repository.search_people(PeopleQuery(uf="SP", office_kind="senator"), as_of, None)
    assert [row["person_id"] for row in matching] == [person_id]
    assert repository.search_people(PeopleQuery(uf="SP"), date(2026, 10, 15), None) == []
    assert repository.search_people(PeopleQuery(q="Identificação privada"), as_of, None) == []
    assert repository.search_people(PeopleQuery(q="%_"), as_of, None) == []
    assert repository.fetch_public_person(person_id)["display_name"] == "Perfil demonstrativo"
    assert len(repository.fetch_current_exercises(person_id, as_of)) == 1
    assert repository.fetch_latest_public_payments(person_id, as_of) == []
    political_party_id = connection.execute(
        "INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id) "
        "VALUES('XYZ','Partido demonstrativo','XYZ',%s) RETURNING id",
        (record_id,),
    ).fetchone()["id"]
    connection.execute(
        "INSERT INTO se_liga_brasil.political_party_affiliation"
        "(person_id,political_party_id,observed_on,source_record_id,evidence_kind) "
        "VALUES(%s,%s,'2026-10-14',%s,'administrative')",
        (person_id, political_party_id, record_id),
    )
    assert repository.fetch_public_affiliations(person_id, as_of)[0]["abbreviation"] == "XYZ"
    assert [
        row["person_id"]
        for row in repository.search_people(PeopleQuery(political_party="xyz"), as_of, None)
    ] == [person_id]
    connection.execute(
        "INSERT INTO se_liga_brasil.person_identity_alias"
        "(alias_person_id,canonical_person_id,source_record_id,resolution_reason) "
        "VALUES(%s,%s,%s,'official_history')",
        (other_id, person_id, record_id),
    )
    assert repository.fetch_public_person(other_id) is None
    assert len(repository.search_people(PeopleQuery(), as_of, None)) == 1
