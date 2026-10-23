"""Fictitious national Senate subjects in isolated rollback-only schemas."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_senado_institutional_profiles import institutional_subject  # noqa: F401

from crawlers.senado.configuration import SenateConfiguration
from crawlers.senado.institutional_profile import normalize_institutional_profile
from crawlers.senado.roster_collection import ingest_national_roster_batch
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import hash_file

pytestmark = pytest.mark.integration


def institutional_artifact(tmp_path, data):
    path = tmp_path / (data["officialSenatorCode"] + ".json")
    path.write_text("{}")
    resource = Resource(
        "fictional-national-" + data["officialSenatorCode"],
        "senado_institutional_profile",
        "https://legis.senado.leg.br/dadosabertos/senador/123456.json",
        "senado_institutional_profile",
        2026,
        "senado-test",
        file_suffix=".json",
    )
    return DownloadedArtifact(
        resource, path, hash_file(path), datetime.now(UTC).isoformat(), path.stat().st_size
    )


def test_national_roster_creates_person_without_candidacy_and_reuses_personal_identity(
    integration_database,
    tmp_path,
    institutional_subject,  # noqa: F811
):
    connection = integration_database
    data = normalize_institutional_profile(*institutional_subject, "2026-10-22")
    artifact = institutional_artifact(tmp_path, data)
    config = SenateConfiguration(tmp_path)
    ingest_national_roster_batch(connection, config, [(artifact, data)])
    person = connection.execute(
        "SELECT id,civil_name,display_name,current_public_office_kind FROM se_liga_brasil.person"
    ).fetchone()
    assert person["civil_name"] == "Pessoa Civil Fictícia"
    assert person["display_name"] == "Pessoa Pública"
    assert person["current_public_office_kind"] == "senator"
    assert (
        connection.execute("SELECT count(*) n FROM se_liga_brasil.electoral_candidacy").fetchone()[
            "n"
        ]
        == 0
    )
    second = data | {"officialSenatorCode": "123457"}
    second_artifact = replace(
        institutional_artifact(tmp_path, second), fetched_at=artifact.fetched_at
    )
    ingest_national_roster_batch(connection, config, [(second_artifact, second)])
    assert connection.execute("SELECT count(*) n FROM se_liga_brasil.person").fetchone()["n"] == 1
    assert (
        connection.execute(
            "SELECT count(*) n FROM se_liga_brasil.person_identifier WHERE namespace='senator'"
        ).fetchone()["n"]
        == 2
    )
    assert (
        connection.execute(
            "SELECT count(*) n FROM se_liga_brasil.political_party_affiliation"
        ).fetchone()["n"]
        == 0
    )
    assert ingest_national_roster_batch(connection, config, [(artifact, data)])[0][
        "skipped_artifact"
    ]
    conflict = data | {"civilName": "Outra Pessoa Fictícia", "birthDate": "1970-01-01"}
    changed = replace(
        artifact,
        resource=replace(artifact.resource, resource_id="changed-fictional"),
        fetched_at=(datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
    )
    with pytest.raises(IngestionError, match="SENATE_INSTITUTIONAL_IDENTITY_CONFLICT"):
        ingest_national_roster_batch(connection, config, [(changed, conflict)])


def test_same_instant_institutional_observation_does_not_duplicate_affiliation(
    integration_database,
    tmp_path,
    institutional_subject,  # noqa: F811
):
    connection = integration_database
    data = normalize_institutional_profile(*institutional_subject, "2026-10-22")
    artifact = institutional_artifact(tmp_path, data)
    config = SenateConfiguration(tmp_path)
    ingest_national_roster_batch(connection, config, [(artifact, data)])
    connection.execute(
        """INSERT INTO se_liga_brasil.political_party(code,name,abbreviation,source_record_id)
        SELECT 'FAKE','Partido fictício','TESTE',primary_record_id
        FROM se_liga_brasil.person LIMIT 1"""
    )
    for code in ("123457", "123458"):
        changed = data | {"officialSenatorCode": code}
        changed_artifact = replace(
            institutional_artifact(tmp_path, changed), fetched_at=artifact.fetched_at
        )
        ingest_national_roster_batch(connection, config, [(changed_artifact, changed)])
    assert (
        connection.execute(
            "SELECT count(*) n FROM se_liga_brasil.political_party_affiliation"
        ).fetchone()["n"]
        == 1
    )
