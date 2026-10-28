"""Fictitious regressions preserve the distinction between narrative and ballot."""

from datetime import date

import pytest

from crawlers.alerj.historical_acquisition import discover_synopsis_documents
from crawlers.alerj.historical_identity import verify_historical_identity
from crawlers.alerj.historical_parsing import classify_narrative, parse_synopsis_pages
from crawlers.alerj.historical_staging import PARSER_VERSION, stage_historical_events
from database.alerj_history import fetch_person_historical_activity, public_historical_event
from service.alerj_history.collection import HistoricalProjectionWriter
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.ingestion.repository import IngestionRepository, verify_staged_record
from storage.files import hash_file, read_json_lines

URL = "https://www2.alerj.rj.gov.br/leideacesso/spic/arquivo/Pessoa_Teste_2018.pdf"
PAGE = """ASSEMBLÉIA LEGISLATIVA DO ESTADO DO RIO DE JANEIRO
Deputado PESSOA TESTE
D.O. Nº 28 de 08/02/2018
1ª Sessão Extraordinária – 07/02/2018
Páginas 6 e 7
Encaminha a votação do Projeto de Lei nº 44/2017, do Deputado Outro.

Registra seu voto contrário ao Projeto de Lei nº 12/2011, do Deputado Outro.

Discursa sobre a aprovação coletiva do Projeto de Lei nº 21/2017.
"""


def test_session_date_is_not_official_journal_publication_date():
    events, failures = parse_synopsis_pages([PAGE], "Pessoa Teste", URL, 2018)
    assert not failures
    assert len(events) == 3
    assert {event["occurredOn"] for event in events} == {"2018-02-07"}
    assert {event["eventType"] for event in events} == {
        "vote_declaration",
        "speech",
        "voting_procedure",
    }
    assert all(event["nominalBallotVerified"] is False for event in events)
    assert events[0]["matter"]["title"] == "PL 44/2017"
    assert events[0]["evidenceUrl"].endswith("#page=1")
    assert events == parse_synopsis_pages([PAGE], "Pessoa Teste", URL, 2018)[0]


def test_other_person_pdf_rejected_before_projection():
    with pytest.raises(IngestionError, match="ALERJ_SYNOPSIS_PERSON_MISMATCH"):
        parse_synopsis_pages([PAGE], "Outra Pessoa", URL, 2018)


def test_invalid_session_date_is_rejected_and_empty_archive_is_not_coverage():
    with pytest.raises(IngestionError, match="ALERJ_SYNOPSIS_NO_DATED_NARRATIVES"):
        parse_synopsis_pages([PAGE.replace("07/02/2018", "31/02/2018")], "Pessoa Teste", URL, 2018)
    events, failures = parse_synopsis_pages(
        [PAGE, PAGE.replace("07/02/2018", "31/02/2018")], "Pessoa Teste", URL, 2018
    )
    assert len(events) == 3
    assert failures[0]["reasonCode"] == "ALERJ_SYNOPSIS_SESSION_DATE_INVALID"


@pytest.mark.parametrize(
    "description",
    [
        "Comenta a aprovação do Projeto de Lei nº 1/2018.",
        "Tece considerações sobre votação unânime.",
        "Declara que a Assembleia aprovou a proposta.",
    ],
)
def test_collective_result_does_not_create_personal_vote(description):
    assert classify_narrative(description) == "legislative_comment"


def test_discovery_uses_official_links_not_generated_year_urls():
    payload = b'<a href="arquivo/Pessoa_Teste_2018.pdf">2018</a>'
    assert discover_synopsis_documents(
        payload, "https://www2.alerj.rj.gov.br/leideacesso/spic/"
    ) == [URL]
    with pytest.raises(IngestionError, match="UNTRUSTED_RESOURCE_URL"):
        discover_synopsis_documents(b'<a href="https://evil.test/a.pdf">PDF</a>', URL)


def test_bridge_requires_same_official_public_name_and_birth(monkeypatch):
    profile = b"<div>DEPUTADO Pessoa Teste</div><h2>NASCIMENTO</h2><p>10 de maio de 1980</p>"
    bridge = {
        "DetalheParlamentar": {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    "NomeCompletoParlamentar": "Pessoa Civil Teste",
                    "NomeParlamentar": "Pessoa Teste",
                },
                "DadosBasicosParlamentar": {"DataNascimento": "1980-05-10"},
            }
        }
    }
    matches = []
    monkeypatch.setattr(
        "crawlers.alerj.historical_identity.match_official_person",
        lambda *args: matches.append(args) or "unique_full_name_birth_date",
    )
    result = verify_historical_identity(None, "test-person", profile, bridge)
    assert result["civilName"] == "Pessoa Civil Teste"
    assert matches[0][1]["nomeCivil"] == "Pessoa Civil Teste"
    bridge["DetalheParlamentar"]["Parlamentar"]["DadosBasicosParlamentar"]["DataNascimento"] = (
        "1981-05-10"
    )
    with pytest.raises(IngestionError, match="ALERJ_HISTORICAL_IDENTITY_BRIDGE_MISMATCH"):
        verify_historical_identity(None, "test-person", profile, bridge)


def make_artifact(tmp_path):
    path = tmp_path / "synopsis.pdf"
    path.write_bytes(b"fictitious PDF bytes for isolated ingestion contract")
    resource = Resource(
        "alerj-history-test",
        "synopsis",
        URL,
        "alerj_historical_synopsis",
        2018,
        "test",
        "RJ",
        ".pdf",
    )
    return DownloadedArtifact(resource, path, hash_file(path), "2026-10-22T12:00:00+00:00", 50)


def test_staging_preserves_distinct_events_and_integrity(tmp_path):
    artifact = make_artifact(tmp_path)
    events, _ = parse_synopsis_pages([PAGE], "Pessoa Teste", URL, 2018)
    rows = [
        event
        | {
            "personId": "test-person",
            "documentSha256": artifact.sha256,
            "storageReference": str(artifact.path),
        }
        for event in events
    ]
    validated = stage_historical_events(artifact, tmp_path, rows, [])
    records = list(read_json_lines(validated.records_path))
    assert len({record["externalKey"] for record in records}) == 3
    for record in records:
        verify_staged_record(record)
    public = public_historical_event(rows[1])
    assert public["action_type"] == "historical_activity"
    assert public["nominal_ballot_verified"] is False
    assert "individual" not in public


@pytest.mark.integration
def test_real_projection_is_idempotent_without_fabricated_votes(integration_database, tmp_path):
    connection = integration_database
    person = connection.execute("""WITH source AS (
      INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
      VALUES('test-history','Fictitious source','https://www.alerj.rj.gov.br','document')
      RETURNING id), record AS (
      INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,
      content_sha256,payload) SELECT id,'fictitious-profile','https://www.alerj.rj.gov.br',
      repeat('a',64),'{}'::jsonb FROM source RETURNING id)
      INSERT INTO se_liga_brasil.person(slug,civil_name,normalized_name,
      display_name,birth_date,primary_record_id)
      SELECT 'pessoa-historical-teste','Pessoa Civil Teste',
      'PESSOA CIVIL TESTE','Pessoa Teste',
      '1980-05-10'::date,id FROM record RETURNING id::text""").fetchone()["id"]
    artifact = make_artifact(tmp_path)
    events, _ = parse_synopsis_pages([PAGE], "Pessoa Teste", URL, 2018)
    rows = [
        event
        | {
            "personId": person,
            "identityMethod": "unique_full_name_birth_date:official_public_name_bridge",
            "documentSha256": artifact.sha256,
            "storageReference": str(artifact.path),
        }
        for event in events
    ]
    validated = stage_historical_events(artifact, tmp_path, rows, [])
    from uuid import uuid4

    from crawlers.alerj.configuration import SOURCE

    repository = IngestionRepository(
        connection, SOURCE, HistoricalProjectionWriter(connection), parser_version=PARSER_VERSION
    )
    repository.begin_run(str(uuid4()), {"purpose": "isolated_regression"})
    try:
        assert repository.ingest_validated_artifact(validated, 500).new == 3
        assert repository.ingest_validated_artifact(validated, 500).skipped_artifact
        result = fetch_person_historical_activity(connection, person, date(2026, 10, 22))
        assert len(result["items"]) == 3
        assert (
            connection.execute("SELECT count(*) count FROM se_liga_brasil.person_vote").fetchone()[
                "count"
            ]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) count FROM se_liga_brasil.proposition_person"
            ).fetchone()["count"]
            == 0
        )
    finally:
        repository.finish_run("completed", {})


@pytest.mark.parametrize("accept", [None, "application/pdf,text/html"])
def test_source_runtime_preserves_explicit_accept_for_pdf(accept, monkeypatch, tmp_path):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from service.voting_pipeline import runtime

    connection = SimpleNamespace(
        execute=lambda *_: SimpleNamespace(fetchone=lambda: {"acquired": True})
    )
    settings = {"storage_directory": tmp_path, "request_timeout_seconds": 30}
    if accept:
        settings["request_accept"] = accept
    observed = []
    monkeypatch.setattr(runtime, "check_source_cooldown", lambda *_: None)
    monkeypatch.setattr(runtime, "local_run_lock", lambda *_: nullcontext())
    monkeypatch.setattr(
        runtime.httpx, "Client", lambda **kwargs: observed.append(kwargs) or nullcontext("client")
    )
    monkeypatch.setattr(runtime, "OfficialHttpClient", lambda *_: "transport")
    with runtime.official_source_acquisition(
        connection,
        SimpleNamespace(**settings),
        SimpleNamespace(code="alerj"),
        (),
        lambda *_: "acquisition",
    ):
        pass
    assert observed[0]["headers"]["Accept"] == (accept or "application/json")
