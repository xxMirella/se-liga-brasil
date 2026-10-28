"""Official full personal evidence creates canonical people, never mandates from roster absence."""

from dataclasses import replace

import pytest

from crawlers.camara.configuration import CrawlerConfiguration
from crawlers.camara.institutional_profile import normalize_institutional_profile
from crawlers.camara.roster_collection import ingest_national_roster_batch
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import hash_content, hash_file, save_json


@pytest.fixture
def institutional_deputy():
    profile = {
        "dados": {
            "id": 900001,
            "nomeCivil": "Pessoa Fictícia Federal",
            "dataNascimento": "1980-02-03",
            "escolaridade": "Superior",
            "ultimoStatus": {
                "nome": "Pessoa Fictícia",
                "siglaUf": "SP",
                "siglaPartido": "TESTE",
                "idLegislatura": 57,
                "situacao": "Exercício",
                "condicaoEleitoral": "Titular",
            },
        }
    }
    return profile, {"id": 900001, "siglaUf": "SP"}


def test_current_observation_does_not_invent_mandate_or_exercise_start(institutional_deputy):
    data = normalize_institutional_profile(*institutional_deputy, "2026-10-23")
    assert data["inExercise"] is True
    assert data["officeKind"] == "federal_deputy"
    assert data["termStart"] is None and data["exerciseStartsOn"] is None


def test_provider_identity_mismatch_is_rejected(institutional_deputy):
    profile, member = institutional_deputy
    with pytest.raises(IngestionError, match="CAMARA_IDENTITY_ROSTER_MISMATCH"):
        normalize_institutional_profile(profile, member | {"id": 900002}, "2026-10-23")


def test_explicit_leave_is_not_counted_as_exercise(institutional_deputy):
    profile, member = institutional_deputy
    profile["dados"]["ultimoStatus"]["situacao"] = "Licença"
    assert normalize_institutional_profile(profile, member, "2026-10-23")["inExercise"] is False


def institutional_artifact(tmp_path, profile):
    path = tmp_path / (hash_content(profile) + ".json")
    save_json(path, profile)
    resource = Resource(
        "test-official-camara",
        "official profile",
        "https://dadosabertos.camara.leg.br/api/v2/deputados/900001",
        "camara_institutional_profile",
        2026,
        "camara-roster",
        file_suffix=".json",
    )
    return DownloadedArtifact(
        resource, path, hash_file(path), "2026-10-23T12:00:00+00:00", path.stat().st_size
    )


@pytest.mark.integration
def test_institutional_identity_reuses_canonical_person_and_never_creates_fake_term(
    integration_database,
    tmp_path,
    institutional_deputy,
):
    profile, member = institutional_deputy
    data = normalize_institutional_profile(profile, member, "2026-10-23")
    artifact = institutional_artifact(tmp_path, profile)
    configuration = CrawlerConfiguration(tmp_path / "data")
    ingest_national_roster_batch(integration_database, configuration, [(artifact, data, profile)])
    ingest_national_roster_batch(integration_database, configuration, [(artifact, data, profile)])
    person = integration_database.execute(
        "SELECT id::text,current_public_office_kind FROM se_liga_brasil.person"
    ).fetchall()
    assert len(person) == 1 and person[0]["current_public_office_kind"] == "federal_deputy"
    assert (
        integration_database.execute(
            "SELECT count(*) n FROM se_liga_brasil.office_term"
        ).fetchone()["n"]
        == 0
    )
    changed = {**data, "displayName": "Outro Nome Público da Mesma Pessoa"}
    changed_artifact = replace(
        artifact, resource=replace(artifact.resource, resource_id="test-second")
    )
    ingest_national_roster_batch(
        integration_database, configuration, [(changed_artifact, changed, profile)]
    )
    assert (
        integration_database.execute("SELECT count(*) n FROM se_liga_brasil.person").fetchone()["n"]
        == 1
    )


@pytest.mark.integration
def test_existing_provider_code_cannot_be_reassigned_to_different_person(
    integration_database,
    tmp_path,
    institutional_deputy,
):
    from copy import deepcopy

    profile, member = institutional_deputy
    data = normalize_institutional_profile(profile, member, "2026-10-23")
    configuration = CrawlerConfiguration(tmp_path / "data")
    ingest_national_roster_batch(
        integration_database,
        configuration,
        [(institutional_artifact(tmp_path, profile), data, profile)],
    )
    changed = deepcopy(profile)
    changed["dados"]["nomeCivil"] = "Outra Pessoa Fictícia Federal"
    changed["dados"]["dataNascimento"] = "1981-04-05"
    changed_data = normalize_institutional_profile(changed, member, "2026-10-23")
    with pytest.raises(IngestionError, match="CAMARA_INSTITUTIONAL_IDENTITY_CONFLICT"):
        ingest_national_roster_batch(
            integration_database,
            configuration,
            [
                (
                    replace(
                        institutional_artifact(tmp_path, changed),
                        fetched_at="2026-10-23T13:00:00+00:00",
                    ),
                    changed_data,
                    changed,
                )
            ],
        )
    assert (
        integration_database.execute("SELECT count(*) n FROM se_liga_brasil.person").fetchone()["n"]
        == 1
    )
