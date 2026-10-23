"""Local ALESP joins use verified personal resolution and preserve temporal uncertainty."""

import json
import sqlite3
import zipfile

import pytest

from crawlers.alesp.institutional_records import institutional_profiles
from crawlers.alesp.local_enrichment import stage_local_records, verified_evidence_references
from crawlers.alesp.local_records import (
    authored_propositions,
    unique_proposition_rows,
    verified_author_index,
    xml_rows,
)
from crawlers.alesp.projection import AlespProjectionWriter
from service.ingestion.contracts import IngestionError
from storage.files import hash_file, read_json_lines


def write_xml(path, payload):
    path.write_text(payload)
    return path


def write_zip(path, payload):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("data.xml", payload)


def example_resolution(person_id="person-one"):
    return {
        "status": "matched",
        "person_id": person_id,
        "official_subjects": [
            {
                "source_subject_id": "42",
                "is_in_office": True,
                "political_party_code": "99",
                "sources": [
                    {
                        "evidence_kind": "profile",
                        "url": "https://www.al.sp.gov.br/test",
                        "sha256": "a",
                        "fetched_at": "2026-10-17T12:00:00+00:00",
                    }
                ],
                "mandates": [
                    {"idLegislatura": 20, "dtInicio": "2023-03-15", "dtTermino": "2027-01-31"}
                ],
            }
        ],
    }


def test_profiles_do_not_turn_legislature_period_into_exercise():
    profile = list(institutional_profiles([example_resolution()]))[0]
    assert profile["inExercise"] is True
    assert profile["mandates"][0]["exerciseStart"] is None
    assert profile["mandates"][0]["termEndExclusive"] == "2027-02-01"
    assert list(institutional_profiles([example_resolution()], {"other-person"})) == []


def test_xml_join_requires_verified_personal_bridge_and_deduplicates(tmp_path):
    write_xml(
        tmp_path / "61_deputados.xml",
        "<Deputados><Deputado><IdDeputado>42</IdDeputado><IdSPL>900</IdSPL></Deputado></Deputados>",
    )
    write_zip(
        tmp_path / "81_documento_autor.zip",
        "<documentos_autores><DocumentoAutor><IdAutor>900</IdAutor><IdDocumento>1</IdDocumento></DocumentoAutor><DocumentoAutor><IdAutor>900</IdAutor><IdDocumento>1</IdDocumento></DocumentoAutor><DocumentoAutor><IdAutor>999</IdAutor><IdDocumento>1</IdDocumento></DocumentoAutor></documentos_autores>",
    )
    write_zip(
        tmp_path / "56_proposituras.zip",
        "<proposituras><propositura><IdDocumento>1</IdDocumento><IdNatureza>1</IdNatureza><AnoLegislativo>2026</AnoLegislativo><NroLegislativo>10</NroLegislativo><DtPublicacao>2026-01-10</DtPublicacao></propositura></proposituras>",
    )
    rows = list(authored_propositions(tmp_path, [example_resolution()]))
    assert len(rows) == 1
    assert rows[0]["personId"] == "person-one"
    assert rows[0]["introducedOn"] is None
    assert rows[0]["role"] == "author"
    assert list(authored_propositions(tmp_path, [], None)) == []
    assert len(list(xml_rows(tmp_path / "61_deputados.xml", "Deputado"))) == 1


def test_ambiguous_person_bridge_is_rejected(tmp_path):
    roster = write_xml(tmp_path / "roster.xml", "<Deputados/>")
    with pytest.raises(IngestionError, match="ALESP_AUTHOR_PERSON_AMBIGUOUS"):
        verified_author_index(roster, [example_resolution(), example_resolution("person-two")])


@pytest.mark.parametrize("conflicting", [False, True])
def test_repeated_proposition_export_rows_are_deduplicated_or_rejected(tmp_path, conflicting):
    second_number = "2" if conflicting else "1"
    path = write_xml(
        tmp_path / "propositions.xml",
        "<proposituras>"
        "<propositura><IdDocumento>42</IdDocumento><NroLegislativo>1</NroLegislativo>"
        "</propositura><propositura><IdDocumento>42</IdDocumento>"
        f"<NroLegislativo>{second_number}</NroLegislativo></propositura></proposituras>",
    )
    with sqlite3.connect(":memory:") as index:
        if conflicting:
            with pytest.raises(IngestionError, match="ALESP_PROPOSITION_EXPORT_CONFLICT"):
                list(unique_proposition_rows(index, path))
        else:
            assert len(list(unique_proposition_rows(index, path))) == 1


def test_evidence_checksum_checked_and_staging_preserves_observation_time(tmp_path):
    source = write_xml(tmp_path / "source.xml", "<Deputados/>")
    resolution = example_resolution()
    resolution["official_subjects"][0]["sources"][0].update(
        {"path": str(source), "sha256": hash_file(source)}
    )
    references = verified_evidence_references([resolution])
    records = list(institutional_profiles([resolution]))
    staged = stage_local_records(
        tmp_path, "alesp_profile", iter(records), references, {"person-one"}
    )
    row = list(read_json_lines(staged.records_path))[0]
    assert row["sourceGeneratedAt"] == "2026-10-17T12:00:00+00:00"
    assert json.loads(staged.artifact.path.read_text())[0]["sha256"] == hash_file(source)
    source.write_text("changed")
    with pytest.raises(IngestionError, match="CHECKSUM_MISMATCH"):
        verified_evidence_references([resolution])


def test_projection_dispatches_snapshot_after_institutional_profile():
    class Writer:
        def __init__(self):
            self.calls = []

        def execute_statements(self, filename, parameters):
            self.calls.append(filename)

    writer = Writer()
    AlespProjectionWriter(writer).project_batch({}, "alesp_profile")
    assert writer.calls == ["alesp_common", "alesp_profile", "person_current_public_office"]


@pytest.mark.integration
def test_local_profile_and_authorship_project_idempotently(
    integration_database, configuration, archive_factory, candidate_row, tmp_path
):
    from datetime import date
    from uuid import uuid4

    from crawlers.alesp.configuration import ALESP_PARSER_VERSION, ALESP_SOURCE
    from crawlers.tse.configuration import TSE_SOURCE
    from crawlers.tse.projection import TseProjectionWriter
    from crawlers.tse.validator import validate_resource
    from service.ingestion.repository import IngestionRepository
    from service.ingestion.sql_batches import SqlBatchWriter
    from storage.validation_index import ValidationIndex

    index = ValidationIndex(tmp_path / "index.sqlite")
    writer = SqlBatchWriter(integration_database)
    tse = IngestionRepository(integration_database, TSE_SOURCE, TseProjectionWriter(writer))
    tse.begin_run(str(uuid4()), {})
    tse.ingest_validated_artifact(
        validate_resource(archive_factory("candidate", [candidate_row]), configuration, index), 500
    )
    person_id = str(
        integration_database.execute("SELECT id FROM se_liga_brasil.person").fetchone()["id"]
    )
    repository = IngestionRepository(
        integration_database,
        ALESP_SOURCE,
        AlespProjectionWriter(writer),
        parser_version=ALESP_PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    try:
        resolution = example_resolution(person_id)
        source = write_xml(tmp_path / "source.xml", "<Deputados/>")
        resolution["official_subjects"][0]["sources"][0].update(
            {
                "path": str(source),
                "sha256": hash_file(source),
                "fetched_at": date.today().isoformat() + "T00:00:00+00:00",
            }
        )
        references = verified_evidence_references([resolution])
        profiles = stage_local_records(
            tmp_path, "alesp_profile", institutional_profiles([resolution]), references, {person_id}
        )
        first = repository.ingest_validated_artifact(profiles, 500)
        assert first.rejected == 0
        assert repository.ingest_validated_artifact(profiles, 500).skipped_artifact
        assert_institutional_projection(integration_database)
        assert_photo_projection(repository, integration_database, tmp_path, references, person_id)
        assert_authorship_projection(
            repository, integration_database, tmp_path, references, person_id
        )
    finally:
        repository.finish_run("completed", {})
        tse.finish_run("completed", {})
        index.close()


def assert_institutional_projection(integration_database):
    person = integration_database.execute(
        "SELECT has_current_public_office,current_public_office_kind FROM se_liga_brasil.person"
    ).fetchone()
    assert person == {
        "has_current_public_office": True,
        "current_public_office_kind": "state_deputy",
    }
    assert (
        integration_database.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.office_exercise"
        ).fetchone()["total"]
        == 0
    )
    assert (
        integration_database.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.office_term"
        ).fetchone()["total"]
        == 1
    )


def assert_authorship_projection(repository, integration_database, tmp_path, references, person_id):
    proposal = {
        "personId": person_id,
        "officialKey": "test-proposal",
        "kind": "PL",
        "number": "1",
        "year": 2026,
        "title": "Proposta fictícia",
        "summary": None,
        "introducedOn": None,
    }
    staged = stage_local_records(
        tmp_path, "alesp_propositions", iter([proposal]), references, {person_id}
    )
    assert repository.ingest_validated_artifact(staged, 500).rejected == 0
    assert repository.ingest_validated_artifact(staged, 500).skipped_artifact
    assert (
        integration_database.execute(
            "SELECT current_status FROM se_liga_brasil.proposition"
        ).fetchone()["current_status"]
        == "unknown"
    )
    assert (
        integration_database.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.proposition_person"
        ).fetchone()["total"]
        == 1
    )


@pytest.mark.integration
def test_multiple_authors_same_proposition_in_batch_and_latest_status_wins(integration_database):
    from datetime import datetime

    from service.ingestion.sql_batches import TEMP_BATCH_SQL, SqlBatchWriter

    database = integration_database
    people, source_record_ids = seed_two_verified_authors(database)
    database.execute(TEMP_BATCH_SQL)
    writer = SqlBatchWriter(database)
    writer.execute_statements("alesp_common", {})
    populate_authorship_batch(database, people, source_record_ids, "2026-10-01", "Original")
    writer.execute_statements("alesp_propositions", {})
    assert (
        database.execute("SELECT count(*) AS n FROM se_liga_brasil.proposition").fetchone()["n"]
        == 1
    )
    assert (
        database.execute("SELECT count(*) AS n FROM se_liga_brasil.proposition_person").fetchone()[
            "n"
        ]
        == 2
    )
    database.execute("TRUNCATE ingestion_batch")
    populate_authorship_batch(database, people, source_record_ids, "2026-10-02", "Atualizada")
    writer.execute_statements("alesp_propositions", {})
    row = database.execute(
        "SELECT summary,status_as_of,source_record_id FROM se_liga_brasil.proposition"
    ).fetchone()
    assert row["summary"] == "Atualizada"
    assert row["status_as_of"].date() == datetime.fromisoformat("2026-10-03").date()
    assert row["source_record_id"] == source_record_ids[1]
    database.execute("TRUNCATE ingestion_batch")
    populate_authorship_batch(database, people, source_record_ids, "2026-09-01", "Antiga")
    writer.execute_statements("alesp_propositions", {})
    assert (
        database.execute("SELECT summary FROM se_liga_brasil.proposition").fetchone()["summary"]
        == "Atualizada"
    )
    assert (
        database.execute("SELECT count(*) AS n FROM se_liga_brasil.proposition_person").fetchone()[
            "n"
        ]
        == 2
    )


def seed_two_verified_authors(database):
    source = database.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('alesp','Teste','https://www.al.sp.gov.br','download') RETURNING id"
    ).fetchone()["id"]
    people, records = [], []
    for index in range(2):
        record = database.execute(
            "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
            "content_sha256,payload) "
            "VALUES(%s,%s,'https://www.al.sp.gov.br',%s,'{}') RETURNING id",
            (source, str(index), str(index) * 64),
        ).fetchone()["id"]
        person = database.execute(
            "INSERT INTO se_liga_brasil.person(slug,civil_name,display_name,primary_record_id) "
            "VALUES(%s,'Pessoa Fictícia','Pessoa Teste',%s) RETURNING id",
            (f"pessoa-{index}", record),
        ).fetchone()["id"]
        people.append(str(person))
        records.append(record)
    return people, records


def populate_authorship_batch(database, people, records, generated_on, summary):
    from datetime import date, timedelta

    from psycopg.types.json import Jsonb

    for index, person_id in enumerate(people):
        data = {
            "personId": person_id,
            "officialKey": "same-proposition",
            "kind": "PL",
            "number": "1",
            "year": 2026,
            "title": "Proposta Fictícia",
            "summary": summary,
            "introducedOn": None,
        }
        generated_at = date.fromisoformat(generated_on) + timedelta(days=index)
        database.execute(
            "INSERT INTO ingestion_batch(normalized_data,source_generated_at,"
            "source_record_id,classification) "
            "VALUES(%s,%s,%s,'new')",
            (Jsonb(data), generated_at, records[index]),
        )


def test_remote_payroll_failure_preserves_local_enrichment(monkeypatch):
    from types import SimpleNamespace

    from crawlers.alesp import enrichment
    from service.ingestion.contracts import IngestionError

    finished = []
    repository = SimpleNamespace(
        begin_run=lambda *args: None,
        finish_run=lambda status, result: finished.append(status),
    )
    monkeypatch.setattr(enrichment, "IngestionRepository", lambda *args, **kwargs: repository)
    monkeypatch.setattr(
        enrichment,
        "collect_alesp_local_enrichment",
        lambda *args: {
            "authorships": {"new": 1},
            "remote_requests": 0,
        },
    )

    def unavailable(*args):
        raise IngestionError("NO_PUBLISHED_PAYROLL_RESOURCES")

    monkeypatch.setattr(enrichment, "run_alesp_pipeline", unavailable)
    result = enrichment.collect_alesp_enrichment(
        None,
        fields={"current_salary", "political_activity"},
    )
    assert result["local_enrichment"]["authorships"]["new"] == 1
    assert result["failures"][0]["code"] == "NO_PUBLISHED_PAYROLL_RESOURCES"
    assert result["status"] == "partial" and finished == ["partial"]


def assert_photo_projection(repository, integration_database, tmp_path, references, person_id):
    photo_rows = [
        {
            "personId": person_id,
            "photoUrl": "https://www3.al.sp.gov.br/legis/biografia/fotos/example.png",
        }
    ]
    photos = stage_local_records(
        tmp_path, "alesp_photos", iter(photo_rows), references, {person_id}
    )
    assert repository.ingest_validated_artifact(photos, 500).new == 1
    assert repository.ingest_validated_artifact(photos, 500).skipped_artifact
    assert (
        integration_database.execute(
            "SELECT photo_url FROM se_liga_brasil.person WHERE id=%s", (person_id,)
        ).fetchone()["photo_url"]
        == photo_rows[0]["photoUrl"]
    )
