"""Fixtures contain fictitious people only; remote integration tests always roll back."""

import csv
import os
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from crawlers.tse.configuration import CrawlerConfiguration
from service.ingestion.contracts import DownloadedArtifact, Resource
from storage.files import hash_file


@pytest.fixture
def candidate_row():
    return {
        "DT_GERACAO": "05/10/2026",
        "HH_GERACAO": "12:00:00",
        "ANO_ELEICAO": "2026",
        "CD_ELEICAO": "1",
        "SQ_CANDIDATO": "10000000001",
        "NR_TURNO": "1",
        "SG_UF": "PA",
        "NM_CANDIDATO": "Pessoa Fictícia",
        "NM_URNA_CANDIDATO": "Pessoa Teste",
        "CD_CARGO": "6",
        "DS_CARGO": "DEPUTADO FEDERAL",
        "DT_NASCIMENTO": "10/05/1980",
        "DS_GRAU_INSTRUCAO": "SUPERIOR COMPLETO",
        "NR_PARTIDO": "99",
        "SG_PARTIDO": "TESTE",
        "NM_PARTIDO": "Partido Fictício",
        "DS_SITUACAO_CANDIDATURA": "APTO",
        "DS_SIT_TOT_TURNO": "#NULO",
        "NR_CPF_CANDIDATO": "12345678900",
    }


@pytest.fixture
def configuration(tmp_path):
    return CrawlerConfiguration(storage_directory=tmp_path / "data", years=(2026,), ufs=("PA",))


@pytest.fixture
def archive_factory(tmp_path):
    def create_archive(kind, rows, *, dataset_year=2026, entry_name=None):
        identifier = uuid4().hex
        resource = Resource(
            identifier,
            kind,
            f"https://cdn.tse.jus.br/{kind}.zip",
            kind,
            dataset_year,
            f"candidatos-{dataset_year}",
        )
        path = tmp_path / f"{identifier}.zip"
        csv_path = tmp_path / f"{identifier}.csv"
        with csv_path.open("w", encoding="latin1", newline="") as output:
            writer = csv.DictWriter(
                output, fieldnames=list(rows[0]), delimiter=";", quoting=csv.QUOTE_ALL
            )
            writer.writeheader()
            writer.writerows(rows)
        with zipfile.ZipFile(path, "w") as archive:
            archive.write(csv_path, entry_name or f"{kind}_{dataset_year}_PA.csv")
        return DownloadedArtifact(
            resource, path, hash_file(path), datetime.now(UTC).isoformat(), path.stat().st_size
        )

    return create_archive


class IsolatedSchemaConnection:
    """Redirect production SQL into a test-only schema without changing repository code."""

    def __init__(self, connection, schema_name):
        self.connection = connection
        self.schema_name = schema_name

    def execute(self, query, parameters=None):
        if parameters and isinstance(parameters, tuple):
            parameters = tuple(
                value.replace("se_liga_brasil:ingestion:", f"{self.schema_name}:ingestion:", 1)
                if isinstance(value, str) and value.startswith("se_liga_brasil:ingestion:")
                else value.replace("se_liga_brasil.", f"{self.schema_name}.", 1)
                if isinstance(value, str) and value.startswith("se_liga_brasil.")
                else value
                for value in parameters
            )
        return self.connection.execute(
            query.replace("se_liga_brasil", self.schema_name), parameters
        )

    def transaction(self):
        return self.connection.transaction()

    def pipeline(self):
        return self.connection.pipeline()


@pytest.fixture
def integration_database():
    if not os.getenv("TEST_DATABASE_URL") and not os.getenv("SE_LIGA_BRASIL_TEST_ENV_FILE"):
        pytest.skip("Set TEST_DATABASE_URL or SE_LIGA_BRASIL_TEST_ENV_FILE for isolated SQL tests")
    import psycopg
    from dotenv import dotenv_values
    from psycopg.rows import dict_row

    from database.operations import read_sql_file, strip_transaction_wrapper

    connection_string = os.getenv("TEST_DATABASE_URL")
    if not connection_string:
        values = dotenv_values(os.environ["SE_LIGA_BRASIL_TEST_ENV_FILE"])
        connection_string = values.get("DATABASE_URL") or values.get("SUPABASE_URL")
    schema_name = f"se_liga_brasil_test_{uuid4().hex[:12]}"
    with (
        psycopg.connect(
            connection_string, autocommit=True, row_factory=dict_row, prepare_threshold=None
        ) as connection,
        connection.transaction(force_rollback=True),
    ):
        isolated = IsolatedSchemaConnection(connection, schema_name)
        isolated.execute(strip_transaction_wrapper(read_sql_file("schema.sql")))
        isolated.execute(
            strip_transaction_wrapper(read_sql_file("migrations/0003_tse_ingestion.sql"))
        )
        isolated.execute(
            strip_transaction_wrapper(read_sql_file("migrations/0004_identity_and_affiliation.sql"))
        )
        isolated.execute(
            strip_transaction_wrapper(
                read_sql_file("migrations/0005_remove_political_party_observation.sql")
            )
        )
        for filename in (
            "0006_payroll_payments.sql",
            "0007_signed_asset_values.sql",
            "0008_internal_person_identity.sql",
            "0009_optional_proposition_year.sql",
            "0010_person_data_gap.sql",
            "0011_source_request_policy.sql",
            "0012_processed_gap_cleanup.sql",
            "0013_person_current_public_office.sql",
            "0014_collection_source_routes.sql",
            "0015_optional_proposition_number.sql",
            "0016_business_relationships.sql",
            "0017_legislative_voting.sql",
            "0018_career_coverage_receipts.sql",
            "0019_voting_refresh_queue.sql",
            "0020_office_legal_scope_versions.sql",
        ):
            isolated.execute(strip_transaction_wrapper(read_sql_file("migrations/" + filename)))
        yield isolated


@pytest.fixture(autouse=True)
def isolated_http_policies():
    from service.acquisition.rate_limit import NEXT_REQUEST_AT, SOURCE_COOLDOWNS

    NEXT_REQUEST_AT.clear()
    SOURCE_COOLDOWNS.clear()
    yield
    NEXT_REQUEST_AT.clear()
    SOURCE_COOLDOWNS.clear()
