"""Historical proofs reject names in invitations, absences and roll-call pauses."""

import json

from crawlers.alesp.participation import parse_participation_reference
from crawlers.alesp.participation_records import participation_identity_indexes
from crawlers.alesp.participation_sources import (
    acquire_participation_sources,
    meeting_document_tasks,
    session_integral_tasks,
)


def reference(tmp_path, payload, kind="minutes", **metadata):
    path = tmp_path / "source"
    path.write_text(payload)
    return {
        "path": str(path),
        "url": "https://www.al.sp.gov.br/ata",
        "sha256": "hash",
        "fetched_at": "2026-11-05T12:00:00Z",
        "kind": kind,
        "event_date": "2025-03-10",
        "event_occurred": True,
        "event_key": "committee:1",
        **metadata,
    }


def test_names_need_explicit_presence_or_actual_speech(tmp_path):
    source = reference(
        tmp_path,
        """
    <p>Estiveram presentes os Deputados Ana Silva e Paulo Santos. Ausente João Lima.</p>
    <p>Ana Silva mencionou Maria Souza. Convidado Pedro Costa.</p>
    <p>O SR. JOÃO LIMA - PSB - (Pausa.)</p>
    <p>O SR. PRESIDENTE - EDUARDO SUPLICY - PT - Declaro aberta a sessão.</p>
    <p>A SRA. MARIA SOUZA - PT - Agradeço a palavra.</p>
    """,
    )
    names = {
        name: name
        for name in [
            "ana silva",
            "paulo santos",
            "joao lima",
            "maria souza",
            "pedro costa",
            "eduardo suplicy",
        ]
    }
    rows = list(parse_participation_reference(source, {}, names))
    assert {row["personId"] for row in rows} == {
        "ana silva",
        "paulo santos",
        "eduardo suplicy",
        "maria souza",
    }
    assert all(row["sourceUrl"] == source["url"] for row in rows)
    assert all(row["date"] == "2025-03-10" for row in rows)


def test_future_or_unconfirmed_events_are_not_proof(tmp_path):
    for metadata in [{"event_date": "2099-01-01"}, {"event_occurred": False}, {"event_date": ""}]:
        source = reference(tmp_path, "<p>Estiveram presentes Ana Silva.</p>", **metadata)
        assert list(parse_participation_reference(source, {}, {"ana silva": "a"})) == []


def test_structured_export_requires_both_registration_and_name(tmp_path):
    payload = {
        "presencasDeputadoReuniao": [
            {
                "idDeputado": 300001,
                "deputado": "Ana Silva",
                "dataReuniao": "2025-03-10",
                "idReuniao": 1,
            },
            {
                "idDeputado": 300001,
                "deputado": "Outra Pessoa",
                "dataReuniao": "2025-03-10",
                "idReuniao": 2,
            },
        ]
    }
    source = reference(tmp_path, json.dumps(payload), "commission_export")
    rows = list(parse_participation_reference(source, {"300001": "a"}, {"ana silva": "a"}))
    assert len(rows) == 1
    assert rows[0]["channel"] == "committee_register"


def test_plenary_only_explicit_present_counts(tmp_path):
    payload = [
        {"idSessaoPlenaria": number, "data": "10/03/2025", "situacao": status}
        for number, status in enumerate(
            ["Presente", "Ausente", "Licença", "Sessão não Deliberativa"], start=1
        )
    ]
    source = reference(tmp_path, json.dumps(payload), "plenary_register", registration="300001")
    rows = list(parse_participation_reference(source, {"300001": "a"}, {}))
    assert len(rows) == 1
    assert rows[0]["eventKey"] == "plenary:1"


def test_ambiguous_names_are_excluded():
    resolutions = [{"status": "unresolved"}] + [
        {
            "status": "matched",
            "person_id": person,
            "official_subjects": [
                {"matricula": registration, "parliamentary_names": ["Ana Silva"]}
            ],
        }
        for person, registration in [("a", "300001"), ("b", "300002")]
    ]
    registrations, names = participation_identity_indexes(resolutions)
    assert len(registrations) == 2
    assert "ana silva" not in names


def test_discovery_ignores_invitation_and_accepts_completed_session():
    documents = [
        {"idTipoDocumento": 37, "linkArquivo": "https://www.al.sp.gov.br/ata.pdf"},
        {"idTipoDocumento": 20011, "linkArquivo": "https://www.al.sp.gov.br/pauta"},
    ]
    meeting = {
        "idReuniao": 1,
        "dtReuniao": "2025-03-10",
        "documentosReuniao": documents,
        "status": {"txNome": "Realizada"},
    }
    assert len(list(meeting_document_tasks({"content": [meeting]}))) == 1
    meeting["status"]["txNome"] = "Convocada"
    assert list(meeting_document_tasks({"content": [meeting]})) == []
    session = {
        "id": 1,
        "dtInicio": "2025-03-10",
        "tipo": "Sessão Solene",
        "temIntegra": True,
        "situacao": "Publicada (Íntegra)",
    }
    assert len(list(session_integral_tasks({"content": [session]}))) == 1


def test_failed_download_is_retried_only_on_next_run(tmp_path):
    class Unavailable:
        calls = 0

        def fetch_bytes(self, *args, **kwargs):
            self.calls += 1
            raise TimeoutError()

    transport = Unavailable()
    result = acquire_participation_sources(tmp_path, transport, {}, max_requests=40)
    assert result["remote_requests"] == 3
    assert transport.calls == 3
    assert result["pending_resources"] == 3


def test_event_list_requires_realized_status_and_matching_identity(tmp_path):
    payload = {
        "idReuniao": 1,
        "dtReuniao": "2025-03-10",
        "status": {"txNome": "Realizada"},
        "parlamentaresPresentes": [{"nuMatricula": 300001, "txNomeParlamentar": "Ana Silva"}],
    }
    source = reference(tmp_path, json.dumps(payload), "meeting_participants")
    rows = list(parse_participation_reference(source, {"300001": "a"}, {"ana silva": "a"}))
    assert rows[0]["channel"] == "event_participants"
    payload["status"]["txNome"] = "Convocada"
    source = reference(tmp_path, json.dumps(payload), "meeting_participants")
    assert list(parse_participation_reference(source, {"300001": "a"}, {"ana silva": "a"})) == []


def test_cache_is_verified_and_ingested_without_network(tmp_path):
    from types import SimpleNamespace

    from crawlers.alesp.local_enrichment import stage_local_records
    from crawlers.alesp.participation import collect_participation_evidence
    from storage.files import hash_file, read_json_lines, save_json

    source = reference(tmp_path, "<p>Estiveram presentes Ana Silva.</p>")
    source["sha256"] = hash_file(tmp_path / "source")
    save_json(tmp_path / "participation/manifest.json", [source])
    resolutions = [
        {
            "status": "matched",
            "person_id": "a",
            "official_subjects": [{"matricula": "300001", "parliamentary_names": ["Ana Silva"]}],
        }
    ]
    artifacts = []
    repository = SimpleNamespace(
        ingest_validated_artifact=lambda artifact, size: artifacts.append(artifact)
    )
    result = collect_participation_evidence(
        repository, tmp_path, resolutions, {"a"}, stage_local_records
    )
    assert result["people_with_evidence"] == 1
    assert len(artifacts) == 1
    staged = list(read_json_lines(artifacts[0].records_path))
    assert staged[0]["normalizedData"]["sourceSha256"] == source["sha256"]


def test_modern_minutes_separate_present_members_from_absent_members(tmp_path):
    source = reference(
        tmp_path,
        """
    <h2>2. Participantes</h2>
    <p>Membros Efetivos presentes:</p><ul><li>Ana Silva</li></ul>
    <p>Membros Substitutos presentes:</p><ul><li>Dr. Jorge do Carmo</li></ul>
    <p>Ausentes:</p><ul><li>Paulo Santos</li></ul>
    <p>Não compareceram Maria Souza.</p>
    """,
    )
    names = {"ana silva": "a", "dr jorge do carmo": "j", "paulo santos": "p", "maria souza": "m"}
    rows = list(parse_participation_reference(source, {}, names))
    assert {row["personId"] for row in rows} == {"a", "j"}


def test_participation_uses_its_own_projection():
    from types import SimpleNamespace

    from crawlers.alesp.projection import AlespProjectionWriter

    statements = []
    writer = SimpleNamespace(execute_statements=lambda name, params: statements.append(name))
    AlespProjectionWriter(writer).project_batch({}, "alesp_participation")
    assert statements == ["alesp_participation"]
