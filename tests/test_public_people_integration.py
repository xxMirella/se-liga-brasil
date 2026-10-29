"""Canonical public SQL runs only in the rollback-only disposable fixture schema."""

from contextlib import nullcontext
from datetime import date

import pytest
from test_public_profile_integration import create_public_read_fixture

from database.public_people import PublicPeopleRepository
from service.public_profile.people import PeopleQuery


@pytest.mark.integration
def test_release_check_serves_people_results_through_wsgi_and_real_sql(
    integration_database, monkeypatch,
):
    from application.vercel import PublicPortalWSGI
    from database import operations
    from service.deployment_validation.public_portal import check_public_search

    create_public_read_fixture(integration_database)
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci:ci@localhost/disposable")
    monkeypatch.setattr(
        operations, "connect_database", lambda *_: nullcontext(integration_database)
    )
    # The fixture already owns a transaction with forced rollback and isolated schema.
    # PostgreSQL cannot change its isolation after fixture creation queries have run.
    monkeypatch.setattr(PublicPeopleRepository, "read_snapshot", lambda _: nullcontext())
    result = check_public_search(PublicPortalWSGI())
    assert len(result["checks"]) == 3
    assert all(check["status"] == 200 for check in result["checks"])


@pytest.mark.integration
@pytest.mark.parametrize("storage_status", [200, 401])
def test_release_checks_activity_with_real_sql_and_authenticated_storage_contract(
    integration_database, monkeypatch, tmp_path, storage_status,
):
    import httpx

    from application import vercel
    from database import operations
    from service.dataset_storage.read import DailyDatasetReader
    from service.dataset_storage.supabase import StorageConfiguration, SupabaseDatasetStorage
    from service.deployment_validation.public_portal import (
        DeploymentValidationError,
        check_public_deployment,
    )

    create_public_read_fixture(integration_database)
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci:ci@localhost/disposable")
    monkeypatch.setenv("SUPABASE_STORAGE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_STORAGE_KEY", "fictitious-test-key")
    monkeypatch.setattr(
        operations, "connect_database", lambda *_: nullcontext(integration_database)
    )
    monkeypatch.setattr(
        "database.public_profile.PublicProfileRepository.read_snapshot", lambda _: nullcontext()
    )
    monkeypatch.setattr(
        "database.public_read_connections.PublicReadConnectionPool.read",
        lambda _pool, operation: operation(integration_database),
    )
    requests = []

    def storage_response(request):
        assert request.headers["apikey"] == "fictitious-test-key"
        requests.append(request.url.path)
        return httpx.Response(storage_status, json={"objects": [], "hasNext": False})

    with httpx.Client(transport=httpx.MockTransport(storage_response)) as client:
        reader = DailyDatasetReader(SupabaseDatasetStorage(
            StorageConfiguration("https://example.supabase.co", "fictitious-test-key"), client
        ), tmp_path / "cache")
        monkeypatch.setattr(vercel, "create_dataset_reader", lambda: reader)
        if storage_status == 200:
            checks = check_public_deployment(vercel.PublicPortalWSGI())["checks"]
            paths = {item["path"] for item in checks}
            assert {"/pessoas", "/api/people", "/panorama", "/api/political-dashboard"} <= paths
            assert any(path.startswith("/pessoas/") for path in paths)
            assert any(path.endswith("/votes") for path in paths)
            assert all(item["status"] == 200 for item in checks)
        else:
            with pytest.raises(DeploymentValidationError, match="PUBLIC_ACTIVITY_HTTP_503"):
                check_public_deployment(vercel.PublicPortalWSGI())
    assert requests == ["/storage/v1/object/list-v2/voting-datasets"]


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


@pytest.mark.integration
def test_current_exercise_respects_term_end_and_explicit_end_observation(integration_database):
    from psycopg.types.json import Jsonb

    connection = integration_database
    person_id, _, record_id, _, _ = create_public_read_fixture(connection)
    repository = PublicPeopleRepository(connection)
    day = date(2026, 10, 14)
    exercise = repository.fetch_current_exercises(person_id, day)[0]
    connection.execute(
        "UPDATE se_liga_brasil.office_term SET term_end=%s WHERE id=%s",
        (day, exercise['term_id']),
    )
    assert repository.fetch_current_exercises(person_id, day) == []
    connection.execute(
        "UPDATE se_liga_brasil.office_term SET term_end=NULL WHERE id=%s",
        (exercise['term_id'],),
    )
    connection.execute(
        "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
        "normalized_value,evidence_kind,review_status,source_record_id) "
        "VALUES(%s,'current_public_office_observation',%s,%s,'administrative','verified',%s)",
        (person_id, Jsonb({}), Jsonb({'institutionCode': exercise['institution_code'],
         'observedOn': day.isoformat(), 'inExercise': False}), record_id),
    )
    assert repository.fetch_current_exercises(person_id, day) == []
    backfill = connection.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,fetched_at,payload) SELECT source_id,'older-reparse',source_url,"
        "repeat('b',64),fetched_at-interval '1 day',payload "
        "FROM se_liga_brasil.source_record WHERE id=%s RETURNING id",
        (record_id,),
    ).fetchone()['id']
    connection.execute(
        "UPDATE se_liga_brasil.office_exercise SET source_record_id=%s WHERE id=%s",
        (backfill, exercise['exercise_id']),
    )
    assert backfill > record_id
    assert repository.fetch_current_exercises(person_id, day) == []
