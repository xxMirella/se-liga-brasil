"""Sitemap SQL sees public changes only; every fictitious row lives inside rollback."""

from uuid import uuid4

import pytest
from test_public_profile_integration import create_public_read_fixture

from database.search_indexing import SearchIndexRepository


@pytest.mark.integration
def test_sitemap_shards_include_new_canonical_people_and_exclude_aliases(integration_database):
    connection = integration_database
    person_id, alias_id, record_id, _, _ = create_public_read_fixture(connection)
    connection.execute(
        "INSERT INTO se_liga_brasil.person_identity_alias "
        "(alias_person_id,canonical_person_id,source_record_id,resolution_reason) "
        "VALUES(%s,%s,%s,'official_history')", (alias_id, person_id, record_id),
    )
    repository = SearchIndexRepository(connection)
    assert sum(row["count"] for row in repository.fetch_person_buckets()) == 1
    rows = repository.fetch_people(person_id[0])
    assert rows == [{"person_id": person_id}]
    new_id = person_id[0] + str(uuid4())[1:]
    connection.execute(
        "INSERT INTO se_liga_brasil.person "
        "(id,slug,civil_name,display_name,primary_record_id) "
        "VALUES(%s,%s,'Pessoa privada fictícia','Perfil público novo',%s)",
        (new_id, new_id, record_id),
    )
    people = {row["person_id"] for row in repository.fetch_people(person_id[0])}
    assert people == {person_id, new_id}
    assert sum(row["count"] for row in repository.fetch_person_buckets()) == 2
    assert all(set(row) == {"person_id"} for row in repository.fetch_people(person_id[0]))
