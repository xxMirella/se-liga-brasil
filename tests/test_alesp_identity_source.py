"""Anonymized source contracts and shared acquisition boundaries for ALESP identities."""

import json
from datetime import UTC, datetime

import pytest

from crawlers.alesp import identity
from crawlers.alesp.configuration import CrawlerConfiguration
from service.ingestion.contracts import DownloadedArtifact, IngestionError
from storage.files import hash_file


def roster_payload():
    return b"""<Deputados><Deputado><IdDeputado>100</IdDeputado><Matricula>300100</Matricula>
    <IdUA>20100</IdUA><NomeParlamentar>Deputada Exemplo</NomeParlamentar>
    <Aniversario>29/02</Aniversario><Partido>EX</Partido></Deputado></Deputados>"""


def telephone_payload():
    return """<h5>GABINETE DEP. <a href='/deputado/?matricula=300100'>Deputada Exemplo</a></h5>
    <p>Responsável: PESSOA CIVIL EXEMPLO</p><!-- <p>Responsável: Outra Pessoa</p> -->
    <p>Cargo: Deputado(a)</p>""".encode("cp1252")


def profile_payload(**overrides):
    payload = {
        "idParlamentar": 100,
        "nuMatricula": 300100,
        "txNomeParlamentar": "Deputada Exemplo",
        "txNomePlenario": None,
        "biografia": {"dtAniversario": "29/02"},
        "isEmExercicio": True,
        "txPartido": "EX",
        "listaFiliacoes": [
            {
                "dtInicio": "2023-03-15",
                "dtFim": None,
                "partido": {"nuLegenda": 10, "dtInicio": "2000-01-01"},
            }
        ],
    }
    return json.dumps(payload | overrides).encode()


def test_telephone_uses_explicit_responsible_and_consistent_matricula():
    evidence = identity.parse_telephone_evidence(telephone_payload(), "300100")
    assert evidence["legal_name"] == "PESSOA CIVIL EXEMPLO"
    assert evidence["membership_evidence"]["role_deputy_confirmed"]
    with pytest.raises(IngestionError, match="MATRICULA_MISMATCH"):
        identity.parse_telephone_evidence(telephone_payload(), "300101")
    with pytest.raises(IngestionError, match="RESPONSIBLE_AMBIGUOUS"):
        identity.parse_telephone_evidence(
            telephone_payload() + b"<p>Respons\xe1vel: Other</p>", "300100"
        )


def test_profile_preserves_source_affiliation_and_checks_subject():
    member = identity.parse_identity_roster(roster_payload())[0]
    evidence = identity.parse_member_profile(profile_payload(), member)
    assert evidence["birthday"] == "29/02"
    assert evidence["political_party_code"] == "10"
    assert evidence["affiliations"][0]["dtInicio"] == "2023-03-15"
    with pytest.raises(IngestionError, match="SUBJECT_MISMATCH"):
        identity.parse_member_profile(profile_payload(idParlamentar=101), member)
    with pytest.raises(IngestionError, match="BIRTHDAY_CONFLICT"):
        identity.parse_member_profile(profile_payload(biografia={"dtAniversario": "01/01"}), member)
    assert identity.normalize_birthday("31/02") is None
    assert identity.normalize_birthday("null") is None
    assert (
        identity.parse_member_profile(profile_payload(biografia=None), member)["birthday"]
        == "29/02"
    )


def test_collection_reuses_one_budget_and_preserves_artifact_evidence(tmp_path, monkeypatch):
    calls = []

    def fake_download(resource, configuration, client, budget):
        calls.append((resource, budget))
        payload = (
            roster_payload()
            if resource.file_suffix == ".xml"
            else profile_payload()
            if resource.file_suffix == ".json"
            else telephone_payload()
        )
        path = tmp_path / (resource.resource_id + resource.file_suffix)
        path.write_bytes(payload)
        return DownloadedArtifact(
            resource, path, hash_file(path), datetime.now(UTC).isoformat(), len(payload)
        )

    monkeypatch.setattr(identity, "download_resource", fake_download)
    result = identity.collect_identity_evidence(CrawlerConfiguration(tmp_path), object())
    assert len(calls) == 3 and len({id(budget) for _, budget in calls}) == 1
    assert result[0]["source_subject_id"] == "100"
    assert result[0]["legal_name"] == "PESSOA CIVIL EXEMPLO"
    assert len(result[0]["sources"]) == 3
    assert result[0]["source_errors"] == []
    assert (tmp_path / "identity-evidence.json").is_file()


def test_collection_exposes_profile_failures_without_inventing_identity(tmp_path, monkeypatch):
    def fake_acquire(resource, configuration, client, budget):
        if resource.file_suffix == ".json":
            raise IngestionError("HTTP_ERROR")
        payload = roster_payload() if resource.file_suffix == ".xml" else telephone_payload()
        return payload, {
            "url": resource.url,
            "sha256": "audit",
            "path": "/local",
            "fetched_at": "2026-10-16T00:00:00Z",
        }

    monkeypatch.setattr(identity, "acquire_identity_resource", fake_acquire)
    result = identity.collect_identity_evidence(CrawlerConfiguration(tmp_path), object())
    assert result[0]["source_errors"][0]["code"] == "HTTP_ERROR"
    assert "is_in_office" not in result[0]
