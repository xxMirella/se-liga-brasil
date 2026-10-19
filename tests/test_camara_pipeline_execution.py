"""Offline collection exercises immutable evidence, payroll and requested capabilities."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_camara_crawler import official_profile, salary_html

from crawlers.camara import pipeline
from crawlers.camara.configuration import CrawlerConfiguration
from service.ingestion.contracts import DownloadedArtifact, IngestionSummary, Resource
from storage.files import hash_file


def artifact(tmp_path, name, payload, kind="camara_profile"):
    path = tmp_path / (name + ".json")
    path.write_bytes(payload if isinstance(payload, bytes) else json.dumps(payload).encode())
    resource = Resource(name, name, "https://www.camara.leg.br/" + name, kind, 2026, "test")
    return DownloadedArtifact(
        resource, path, hash_file(path), datetime.now(UTC).isoformat(), path.stat().st_size
    )


def test_profile_downloads_preserve_originals_and_bundle_all_identity_evidence(
    monkeypatch, tmp_path
):
    official = official_profile("Pessoa Fictícia")
    documents = {
        "deputados/1": {"dados": official},
        "deputados/1/historico": {
            "dados": [
                {"idLegislatura": 57, "dataHora": "2023-02-01T12:00", "situacao": "Exercício"}
            ]
        },
        "legislaturas/57": {
            "dados": {"id": 57, "dataInicio": "2023-02-01", "dataFim": "2027-01-31"}
        },
    }
    originals = {
        path: artifact(tmp_path, str(position), data)
        for position, (path, data) in enumerate(documents.items())
    }
    acquisition = SimpleNamespace(
        configuration=CrawlerConfiguration(tmp_path),
        json_document=lambda path, _kind: (documents[path], originals[path]),
    )
    monkeypatch.setattr(pipeline, "match_official_person", lambda *_: "validated_cpf")
    profile, bundle = pipeline.collect_person_profile(
        acquisition, None, {"person_id": "person"}, {"id": 1}
    )
    assert profile["personId"] == "person" and len(profile["evidence"]) == 3
    assert len(json.loads(bundle.path.read_text())) == 3
    assert all(hash_file(a.path) == a.sha256 for a in originals.values())
    repeated = pipeline.bundle_profile_artifacts(acquisition, list(originals.values()))
    assert repeated.path == bundle.path


@pytest.mark.parametrize("published", [False, True])
def test_salary_collection_uses_latest_published_month_without_inventing_payment(
    monkeypatch, tmp_path, published
):
    index = artifact(
        tmp_path, "index", b'<a href="?mesAno=092026">M</a>' if published else b"No payroll"
    )
    salary = artifact(tmp_path, "salary", salary_html(), "camara_payroll")
    acquisition = SimpleNamespace(
        configuration=CrawlerConfiguration(tmp_path),
        acquire=lambda _u, kind, _s: index if kind == "camara_salary_index" else salary,
    )
    ingested = []
    monkeypatch.setattr(
        pipeline, "ingest_collected", lambda _r, _a, _f, rows: ingested.extend(rows) or {"new": 1}
    )
    result = pipeline.collect_current_salary(
        acquisition,
        None,
        {"id": 1},
        {
            "personId": "person",
            "displayName": "Pessoa Teste",
            "representedUf": "SP",
        },
    )
    if published:
        assert result["competence"] == "2026-09-01" and ingested[0]["grossAmount"] == "1000.00"
    else:
        assert result["status"] == "not_published" and not ingested


def test_shared_authored_documents_are_listed_and_details_are_bounded(monkeypatch, tmp_path):
    from service.legislative_collection import sources

    saved = []
    page = [
        {
            "uri": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/1",
            "siglaTipo": "PEC",
            "numero": 1,
            "ano": 2025,
        }
    ]
    acquisition = SimpleNamespace(
        configuration=CrawlerConfiguration(tmp_path),
        pages=lambda *_: iter([(page, None), ([], None)]),
    )
    monkeypatch.setattr(pipeline, "ingest_collected", lambda _r, _a, _f, rows: saved.extend(rows))
    monkeypatch.setattr(
        "database.legislative_collection.select_proposition_keys", lambda *_a, **_k: ["doc"]
    )
    calls = []
    monkeypatch.setattr(
        sources, "camara_pipeline", lambda *_a, **kw: calls.append(kw) or {"documents": []}
    )
    result = pipeline.collect_authored_propositions(
        acquisition, SimpleNamespace(connection=None), {"id": 1}, "person"
    )
    assert result["records"] == 1 and result["pages"] == 2
    assert saved[0]["personId"] == "person"
    assert calls == [{"keys": ["doc"], "maximum": 25}]


def test_profile_staging_serializes_only_validated_artifact_and_ingestion_summary(tmp_path):
    source = artifact(tmp_path, "profile", {})
    received = []
    repository = SimpleNamespace(
        ingest_validated_artifact=lambda data, budget: (
            received.append((data, budget)) or IngestionSummary(new=1)
        )
    )
    acquisition = SimpleNamespace(configuration=CrawlerConfiguration(tmp_path))
    result = pipeline.ingest_collected(repository, acquisition, source, [{"personId": "person"}])
    assert result["new"] == 1 and received[0][1] == 500
    assert received[0][0].summary["valid"] == 1


def test_attendance_request_does_not_expand_into_salary_or_proposition_crawl(monkeypatch):
    from crawlers.camara import attendance

    monkeypatch.setattr(pipeline, "collect_person_profile", lambda *_: ({}, None))
    monkeypatch.setattr(pipeline, "ingest_collected", lambda *_: {})
    monkeypatch.setattr(attendance, "collect_attendance_history", lambda *_: {"years": []})
    result = pipeline.enrich_person(
        None,
        SimpleNamespace(connection=None),
        {"person_id": "p", "requested_fields": ["attendance"]},
        {},
    )
    assert result == {"person_id": "p", "profile": {}, "attendance": {"years": []}}
