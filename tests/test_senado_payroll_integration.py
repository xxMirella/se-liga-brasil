"""Monthly salaries reconcile idempotently with isolated per-person staging."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from test_senado_nominal_payroll import PERIOD, PROFILE, payroll_row

from crawlers.senado.configuration import PARSER_VERSION, SOURCE, SenateConfiguration
from crawlers.senado.payroll import normalize_monthly_salary
from crawlers.senado.projection import SenateProjectionWriter
from crawlers.senado.staging import stage_records
from service.ingestion.contracts import DownloadedArtifact, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file


@pytest.fixture
def salary_repository(integration_database):
    repository = IngestionRepository(
        integration_database,
        SOURCE,
        SenateProjectionWriter(SqlBatchWriter(integration_database)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    record_id = integration_database.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,payload) VALUES(%s,'identity','https://www.senado.leg.br',%s,'{}') "
        "RETURNING id",
        (repository.source_id, "a" * 64),
    ).fetchone()["id"]
    people = [str(uuid4()), str(uuid4())]
    for person_id in people:
        integration_database.execute(
            "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
            "VALUES(%s,%s,'Pessoa Fictícia','Pessoa Fictícia',%s)",
            (person_id, person_id, record_id),
        )
    try:
        yield repository, people
    finally:
        repository.finish_run("completed", {})


def salary_artifact(tmp_path, timestamp, row):
    path = tmp_path / f"{uuid4()}.json"
    path.write_text(json.dumps([row]))
    resource = Resource(
        "senado-payroll-2026-09",
        "Senate payroll",
        "https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/2026/9",
        "senado_payroll",
        2026,
        "senado-enrichment",
        file_suffix=".json",
    )
    return DownloadedArtifact(
        resource, path, hash_file(path), timestamp.isoformat(), path.stat().st_size
    )


@pytest.mark.integration
def test_monthly_salary_staging_isolated_and_corrections_preserve_one_payment(
    salary_repository,
    tmp_path,
):
    repository, people = salary_repository
    configuration = SenateConfiguration(tmp_path)
    timestamp = datetime.now(UTC)
    artifact = salary_artifact(tmp_path, timestamp, payroll_row())
    salaries = [
        normalize_monthly_salary([(1, payroll_row())], PROFILE | {"personId": person}, "77", PERIOD)
        for person in people
    ]
    staged = [stage_records(artifact, configuration, [salary]) for salary in salaries]
    assert staged[0].records_path != staged[1].records_path
    assert repository.ingest_validated_artifact(staged[0], 100).new == 1
    assert repository.ingest_validated_artifact(staged[1], 100).new == 1
    assert repository.ingest_validated_artifact(staged[0], 100).skipped_artifact
    correction = payroll_row(
        sequencial=88, remuneracao_basica="1.100,00", remuneracao_liquida="930,00"
    )
    updated = salary_artifact(tmp_path, timestamp + timedelta(seconds=1), correction)
    salary = normalize_monthly_salary(
        [(1, correction)], PROFILE | {"personId": people[0]}, "88", PERIOD
    )
    assert (
        repository.ingest_validated_artifact(
            stage_records(updated, configuration, [salary]), 100
        ).changed
        == 1
    )
    rows = repository.connection.execute(
        "SELECT person_id::text,gross_amount,tax_amount,net_amount,identity_status,office_kind "
        "FROM se_liga_brasil.person_payroll_payment ORDER BY net_amount DESC"
    ).fetchall()
    assert len(rows) == 2 and rows[0]["person_id"] == people[0]
    assert str(rows[0]["gross_amount"]) == "1080.00" and str(rows[0]["net_amount"]) == "930.00"
    assert all(r["identity_status"] == "verified" and r["office_kind"] == "senator" for r in rows)


@pytest.mark.integration
@pytest.mark.parametrize("prefix", ["senado_profile", "senado_institutional_profile"])
def test_stored_payroll_profiles_require_matching_canonical_birth_and_verified_identity(
    salary_repository, prefix,
):
    from database.senado_payroll import fetch_verified_payroll_profiles

    repository, people = salary_repository
    connection = repository.connection
    for position, person in enumerate(people):
        connection.execute(
            "UPDATE se_liga_brasil.person SET birth_date='1980-01-02' WHERE id=%s", (person,)
        )
        profile = PROFILE | {
            "personId": person, "birthDate": "1980-01-02" if position == 0 else "1981-01-02",
            "identityMethod": "unique_full_name_birth_date",
        }
        record = connection.execute(
            "SELECT primary_record_id FROM se_liga_brasil.person WHERE id=%s", (person,)
        ).fetchone()["primary_record_id"]
        connection.execute(
            "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
            "normalized_value,source_record_id,review_status,evidence_kind) "
            "VALUES(%s,%s,%s,%s,%s,'verified','administrative')",
            (person, f"{prefix}:{position}", Jsonb(profile), Jsonb(profile), record),
        )
    profiles = fetch_verified_payroll_profiles(connection, PERIOD)
    assert [profile["personId"] for profile in profiles] == [people[0]]
    assert profiles[0]["evidence"][0]["sourceRecordId"] is not None
    assert fetch_verified_payroll_profiles(connection, PERIOD, person_id=people[1]) == []
