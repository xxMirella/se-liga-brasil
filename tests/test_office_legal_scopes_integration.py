"""All legal-scope test writes are isolated and rolled back by the database fixture."""

from copy import deepcopy
from datetime import date

import pytest
from test_public_profile_integration import create_public_read_fixture

from database.office_legal_scopes import fetch_public_office_scopes, ingest_office_legal_scopes
from database.operations import read_sql_file, strip_transaction_wrapper
from service.office_duties.legal_catalog import build_legal_scope_records, scope_record_hash


def install_scope_schema(connection):
    connection.execute(
        strip_transaction_wrapper(
            read_sql_file(
                "migrations/0020_office_legal_scope_versions.sql",
            )
        )
    )


@pytest.mark.integration
def test_catalog_ingestion_replay_hash_conflict_and_rls(integration_database):
    connection = integration_database
    install_scope_schema(connection)
    records = build_legal_scope_records()
    assert ingest_office_legal_scopes(connection, records) == {"inserted": 14, "unchanged": 0}
    assert ingest_office_legal_scopes(connection, records) == {"inserted": 0, "unchanged": 14}
    altered = deepcopy(records[0])
    altered["limitations"].append("Different content under an existing version")
    altered["content_sha256"] = scope_record_hash(altered)
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        ingest_office_legal_scopes(connection, [altered])
    stored = connection.execute(
        "SELECT content_sha256 FROM se_liga_brasil.office_legal_scope_version "
        "WHERE office_kind=%s AND jurisdiction=%s AND catalog_version=%s",
        (records[0]["office_kind"], records[0]["jurisdiction"], records[0]["catalog_version"]),
    ).fetchone()
    assert stored["content_sha256"] == records[0]["content_sha256"]
    security = connection.execute(
        "SELECT relrowsecurity FROM pg_class WHERE oid="
        "'se_liga_brasil.office_legal_scope_version'::regclass",
    ).fetchone()
    assert security["relrowsecurity"] is True
    grants = connection.execute(
        "SELECT count(*) AS grants FROM information_schema.role_table_grants "
        "WHERE table_schema=%s AND table_name='office_legal_scope_version' "
        "AND grantee IN ('PUBLIC','anon','authenticated')",
        (connection.schema_name,),
    ).fetchone()
    assert grants["grants"] == 0


@pytest.mark.integration
def test_public_catalog_read_does_not_infer_current_exercise_or_historical_validity(
    integration_database,
):
    connection = integration_database
    install_scope_schema(connection)
    person_id, *_ = create_public_read_fixture(connection)
    ingest_office_legal_scopes(connection, build_legal_scope_records())
    records = fetch_public_office_scopes(connection, person_id, date(2026, 10, 18))
    assert records and records[0]["office_kind"] == "senator"
    assert records[0]["competencies"]
    assert records[0]["association_status"] == "observed_office_not_current_exercise"
    assert records[0]["temporal_status"] == "legal_validity_not_established"
    assert records[0]["legal_valid_from"] is None
    historical = fetch_public_office_scopes(connection, person_id, date(2020, 1, 1))
    assert historical[0]["coverage_status"] == "unclassified"
    assert historical[0]["competencies"] == []
