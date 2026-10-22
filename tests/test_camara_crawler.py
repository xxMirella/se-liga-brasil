import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_database_integration import start_repository

from crawlers.camara.configuration import PARSER_VERSION, SOURCE, CrawlerConfiguration
from crawlers.camara.normalization import normalize_profile, normalize_proposition
from crawlers.camara.payroll import normalize_salary
from crawlers.camara.projection import CamaraProjectionWriter
from crawlers.camara.staging import stage_records
from crawlers.tse.validator import validate_resource
from database.completeness import fetch_completeness_rows
from database.enrichment import match_official_person
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file
from storage.validation_index import ValidationIndex


def salary_html(name="Pessoa Teste", net="900,00"):
    return f"""<h1>{name}</h1><table><caption>09/2026 -FOLHA NORMAL</caption>
    <tr><td>1 - Remuneração Básica</td></tr><tr><td>a - Remuneração Fixa</td><td>1.000,00</td></tr>
    <tr><td>4 - Descontos Obrigatórios</td></tr><tr><td>a - Imposto</td><td>-100,00</td></tr>
    <tr><td>5 - Remuneração após Descontos</td></tr>
    <tr><td>a - Remuneração após Descontos</td><td>{net}</td></tr>
    <tr><td>6 - Outros</td></tr><tr><td>a - Auxílios</td><td>50,00</td></tr></table>""".encode()


def test_salary_reconciliation_excludes_allowances_and_rejects_wrong_person():
    profile = {"personId": "p", "displayName": "Pessoa Teste", "representedUf": "SP"}
    row = normalize_salary(salary_html(), "2026-09", profile)
    assert (row["grossAmount"], row["taxAmount"], row["netAmount"]) == (
        "1000.00",
        "100.00",
        "900.00",
    )
    with pytest.raises(IngestionError, match="PERSON_MISMATCH"):
        normalize_salary(salary_html("Outro Nome"), "2026-09", profile)
    with pytest.raises(IngestionError, match="RECONCILIATION_FAILED"):
        normalize_salary(salary_html(net="950,00"), "2026-09", profile)


def ingest_rows(repository, configuration, kind, rows):
    path = configuration.storage_directory / (kind + ".json")
    path.write_text(json.dumps(rows))
    resource = Resource(
        kind,
        kind,
        "https://dadosabertos.camara.leg.br/test",
        kind,
        2026,
        "test",
        file_suffix=".json",
    )
    artifact = DownloadedArtifact(
        resource, path, hash_file(path), datetime.now(UTC).isoformat(), path.stat().st_size
    )
    validated = stage_records(artifact, configuration, rows)
    first = repository.ingest_validated_artifact(validated, 500)
    assert repository.ingest_validated_artifact(validated, 500).skipped_artifact
    return first


@pytest.mark.integration
def test_verified_enrichment_preserves_person_and_links_payroll_and_authorship(
    integration_database, configuration, archive_factory, candidate_row, tmp_path
):
    tse = start_repository(integration_database)
    index = ValidationIndex(tmp_path / "tse.sqlite")
    candidate = candidate_row | {"NR_CPF_CANDIDATO": "52998224725"}
    tse.ingest_validated_artifact(
        validate_resource(archive_factory("candidate", [candidate]), configuration, index), 500
    )
    person = integration_database.execute("SELECT id FROM se_liga_brasil.person").fetchone()
    person_id = str(person["id"])
    camara = IngestionRepository(
        integration_database,
        SOURCE,
        CamaraProjectionWriter(SqlBatchWriter(integration_database)),
        parser_version=PARSER_VERSION,
    )
    camara.begin_run(str(uuid4()), {})
    official = official_profile(candidate["NM_CANDIDATO"])
    try:
        method = match_official_person(integration_database, official, person_id)
        history = [{"idLegislatura": 57, "dataHora": "2023-02-01T12:00", "situacao": "Exercício"}]
        profile = normalize_profile(
            official,
            history,
            {"id": 57, "dataInicio": "2023-02-01", "dataFim": "2027-01-31"},
            person_id,
            method,
        )
        config = CrawlerConfiguration(tmp_path)
        assert ingest_rows(camara, config, "camara_profile", [profile]).rejected == 0
        verify_derived_exercise(camara, config, profile, integration_database)
        assert (
            ingest_rows(
                camara,
                config,
                "camara_payroll",
                [normalize_salary(salary_html(), "2026-09", profile)],
            ).rejected
            == 0
        )
        proposal = example_proposition(person_id)
        proposal.update(number=None, year=None)
        assert ingest_rows(camara, config, "camara_propositions", [proposal]).rejected == 0
        assert (
            integration_database.execute(
                "SELECT count(*) AS total FROM se_liga_brasil.person"
            ).fetchone()["total"]
            == 1
        )
        row = fetch_completeness_rows(integration_database, person_id)[0]
        assert row["current_party"] and row["current_office"] and row["has_propositions"]
        proposition = integration_database.execute(
            "SELECT current_status,number,year FROM se_liga_brasil.proposition"
        ).fetchone()
        assert proposition == {"current_status": "unknown", "number": None, "year": None}
    finally:
        camara.finish_run("completed", {})
        tse.finish_run("completed", {})
        index.close()


def official_profile(civil_name):
    return {
        "nomeCivil": civil_name,
        "cpf": "52998224725",
        "dataNascimento": "1980-05-10",
        "escolaridade": "Superior",
        "ultimoStatus": {
            "nome": "Pessoa Teste",
            "siglaPartido": "TESTE",
            "siglaUf": "SP",
            "idLegislatura": 57,
            "situacao": "Exercício",
            "condicaoEleitoral": "Titular",
        },
    }


def example_proposition(person_id):
    return normalize_proposition(
        {
            "uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/test",
            "siglaTipo": "PL",
            "numero": 1,
            "ano": 2026,
            "ementa": "Proposta fictícia",
        },
        person_id,
    )


def test_source_zero_year_is_unknown_not_invented_from_publication_date():
    row = {
        "uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/test",
        "siglaTipo": "VTS",
        "numero": 1,
        "ano": 0,
        "ementa": None,
        "dataApresentacao": "2023-04-01",
    }
    normalized = normalize_proposition(row, "p")
    assert normalized["year"] is None
    assert normalized["title"] == "VTS 1"
    assert normalized["introducedOn"] == "2023-04-01"


def test_unnumbered_report_preserves_null_without_discarding_authorship():
    data = normalize_proposition(
        {
            "uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/example",
            "siglaTipo": "PRL",
            "numero": None,
            "ano": 0,
            "ementa": "Parecer fictício",
        },
        "internal-person",
    )
    assert data["number"] is None and data["year"] is None
    assert data["title"] == "PRL"
    assert data["role"] == "author"


def verify_derived_exercise(repository, configuration, profile, connection):
    assert ingest_rows(repository, configuration, "camara_exercise", [profile]).rejected == 0
    exercise = connection.execute("SELECT starts_on FROM se_liga_brasil.office_exercise").fetchall()
    assert len(exercise) == 1
    assert exercise[0]["starts_on"].isoformat() == "2023-02-01"
    connection.execute(
        "INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,"
        "observed_on,source_record_id,information_valid_from,information_scope,evidence_kind) "
        "SELECT a.person_id,a.political_party_id,a.observed_on,e.source_record_id,"
        "a.information_valid_from,a.information_scope,a.evidence_kind "
        "FROM se_liga_brasil.political_party_affiliation a "
        "CROSS JOIN se_liga_brasil.office_exercise e "
        "WHERE a.information_scope='institution:camara'"
    )
    duplicate = dict(profile, photoUrl="https://www.camara.leg.br/another-photo.jpg")
    assert ingest_rows(repository, configuration, "camara_profile", [duplicate]).rejected == 0
    periods = connection.execute(
        "SELECT information_valid_from,information_valid_until "
        "FROM se_liga_brasil.political_party_affiliation "
        "WHERE information_scope='institution:camara'"
    ).fetchall()
    assert all(row['information_valid_until'] is None or
               row['information_valid_until'] > row['information_valid_from'] for row in periods)
