"""Versioned cabinet costs preserve corrections and do not duplicate repeated imports."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from crawlers.senado.cabinet_payroll import cabinet_month_record
from crawlers.senado.cabinet_staging import (
    PARSER_VERSION,
    CabinetPayrollProjectionWriter,
    stage_cabinet_payroll,
)
from crawlers.senado.configuration import SOURCE, SenateConfiguration
from database.cabinet_payroll import fetch_cabinet_payroll_history
from service.cabinet_payroll.public_projection import public_cabinet_payroll
from service.ingestion.contracts import DownloadedArtifact, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file


@pytest.fixture
def cabinet_repository(integration_database):
    db = integration_database
    repository = IngestionRepository(
        db,
        SOURCE,
        CabinetPayrollProjectionWriter(SqlBatchWriter(db)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    record = db.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,payload) VALUES(%s,'identity','https://www.senado.leg.br',%s,'{}') "
        "RETURNING id",
        (repository.source_id, "a" * 64),
    ).fetchone()["id"]
    person_id = str(uuid4())
    db.execute(
        "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
        "VALUES(%s,%s,'Pessoa Fictícia','Pessoa Fictícia',%s)",
        (person_id, person_id, record),
    )
    try:
        yield repository, person_id
    finally:
        repository.finish_run("completed", {})


def stage_month(tmp_path, person_id, total, timestamp):
    from decimal import Decimal

    path = tmp_path / f"{uuid4()}.csv"
    path.write_text(str(total))
    resource = Resource(
        "senado-payroll-2026-09",
        "Folha",
        "https://www.senado.leg.br/payroll-202609.csv",
        "senado_cabinet_payroll",
        2026,
        "senado-cabinet-payroll",
        file_suffix=".csv",
    )
    artifact = DownloadedArtifact(
        resource, path, hash_file(path), timestamp.isoformat(), path.stat().st_size
    )
    roles = {
        "ASSESSOR": {
            "gross_amount": Decimal(total),
            "allowances_amount": Decimal(0),
            "total_amount": Decimal(total),
            "payment_entries": 1,
        }
    }
    data = cabinet_month_record(person_id, "2026-09", roles, artifact)
    return stage_cabinet_payroll(artifact, SenateConfiguration(tmp_path), [data])


@pytest.mark.integration
def test_reimports_corrections_and_as_of_never_duplicate_month(cabinet_repository, tmp_path):
    repository, person_id = cabinet_repository
    timestamp = datetime.now(UTC)
    first = stage_month(tmp_path, person_id, "1000.00", timestamp)
    assert repository.ingest_validated_artifact(first, 100).new == 1
    assert repository.ingest_validated_artifact(first, 100).skipped_artifact
    second = stage_month(tmp_path, person_id, "1200.00", timestamp + timedelta(seconds=1))
    assert repository.ingest_validated_artifact(second, 100).changed == 1
    data = fetch_cabinet_payroll_history(repository.connection, person_id, date(2026, 10, 22))
    public = public_cabinet_payroll(data)
    assert len(public["months"]) == 1
    assert public["latest"]["total_amount"] == "1200.00"
    assert not fetch_cabinet_payroll_history(repository.connection, person_id, date(2026, 8, 31))[
        "months"
    ]
    versions = repository.connection.execute(
        "SELECT count(*) total FROM se_liga_brasil.person_fact WHERE person_id=%s", (person_id,)
    ).fetchone()["total"]
    assert versions == 2
