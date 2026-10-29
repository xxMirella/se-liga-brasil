"""Collection preserves evidence, avoids repeated conversion and deduplicates authorship."""

import csv
import gzip
import hashlib
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

from crawlers.party_documents import discourse_extraction


def load_collection_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_discourse_converts_once_and_keeps_page_article_and_deduplication(monkeypatch):
    calls = []
    paragraph = "Defendemos a saude publica e a educacao em todo o territorio nacional."
    pages = ["Art. 1\n\n" + paragraph, paragraph + "\n\nArt. 2\n\n" + paragraph]
    monkeypatch.setattr(
        discourse_extraction, "pages_of", lambda entry: calls.append(entry) or pages
    )
    entry = {
        "arquivo": "evidence.pdf",
        "sha256": "digest",
        "tipo": "programa",
        "url": "https://example.org/evidence.pdf",
        "data_do_documento": "2000-01-01",
    }
    result = discourse_extraction.extract_discourse(entry)
    matches = discourse_extraction.extract_matches(
        entry, re.compile("saude"), 3, document_pages=pages
    )
    assert len(calls) == 1
    assert matches == [{"trecho": paragraph, "localizador": "p. 1; Art. 1"}]
    assert result["arquivo"] == entry["arquivo"]
    assert result["sha256"] == entry["sha256"]


def test_no_excerpt_limit_does_not_open_document(monkeypatch):
    def unexpected_read(entry):
        raise AssertionError("zero excerpts must not read the document")

    monkeypatch.setattr(discourse_extraction, "pages_of", unexpected_read)
    assert discourse_extraction.extract_matches({}, re.compile("text"), 0) == []


def write_compressed_csv(path, columns, rows):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def camara_authorship_fixture(folder):
    write_compressed_csv(
        folder / "proposicoes-2000.csv.gz",
        ["id", "siglaTipo"],
        [
            {"id": "1", "siglaTipo": "PL"},
            {"id": "2", "siglaTipo": "RIC"},
            {"id": "3", "siglaTipo": "IGNORED"},
        ],
    )
    write_compressed_csv(
        folder / "proposicoesTemas-2000.csv.gz",
        ["uriProposicao", "tema"],
        [
            {"uriProposicao": "/proposicoes/1", "tema": "Saude"},
            {"uriProposicao": "/proposicoes/1", "tema": "Saude"},
            {"uriProposicao": "/proposicoes/1", "tema": "Educacao"},
        ],
    )
    columns = ["tipoAutor", "idProposicao", "siglaPartidoAutor", "proponente"]
    values = [
        ("Deputado(a)", "1", "AA", "1"),
        ("Deputado(a)", "1", "AA", "0"),
        ("Deputado(a)", "1", "BB", "0"),
        ("Deputado(a)", "2", "", "1"),
        ("Deputado(a)", "3", "AA", "1"),
        ("Deputado(a)", "missing", "AA", "1"),
        ("Comissao", "1", "CC", "1"),
    ]
    write_compressed_csv(
        folder / "proposicoesAutores-2000.csv.gz",
        columns,
        [dict(zip(columns, value, strict=True)) for value in values],
    )


def test_camara_counts_unique_propositions_and_separates_proponent(tmp_path):
    module = load_collection_script("collect_party_policy_projects")
    camara_authorship_fixture(tmp_path)
    rows = module.aggregate_camara_year(2000, tmp_path)
    counts = {
        (political_party, group, theme, metric): count
        for _, political_party, group, theme, metric, count in rows
    }
    assert counts["AA", "projeto_de_lei", "Saude", "proposicoes_assinadas"] == 1
    assert counts["AA", "projeto_de_lei", "__total__", "proposicoes_como_proponente"] == 1
    assert counts["BB", "projeto_de_lei", "Educacao", "proposicoes_assinadas"] == 1
    assert not any(
        key[0] in {"BB", "CC"} and key[-1] == "proposicoes_como_proponente" for key in counts
    )
    assert (
        counts[
            "SEM_PARTIDO_REGISTRADO",
            "requerimento_de_informacao",
            "__sem_tema_oficial__",
            "proposicoes_assinadas",
        ]
        == 1
    )
    assert not any(key[1] == "IGNORED" for key in counts)


def test_verified_document_cache_does_not_request_network(tmp_path, monkeypatch):
    module = load_collection_script("archive_party_discourse")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    content = b"archived official original"
    (tmp_path / "document.pdf").write_bytes(content)
    entry = {
        "partido": "AA",
        "tipo": "estatuto",
        "url": "https://example.org/document",
        "arquivo": "document.pdf",
        "status": "obtained",
        "sha256": hashlib.sha256(content).hexdigest(),
    }

    def unexpected_download(url):
        raise AssertionError("valid cache must not request the document again")

    monkeypatch.setattr(module, "download", unexpected_download)
    module.fetch_source({"documents": [entry]}, "AA", "estatuto", entry["url"])
    (tmp_path / "document.pdf").write_bytes(b"changed")
    assert not module.cached_document_is_valid(
        {"documents": [entry]}, "AA", "estatuto", entry["url"]
    )


def test_document_download_is_bounded(monkeypatch):
    module = load_collection_script("archive_party_discourse")
    monkeypatch.setattr(module, "MAX_DOCUMENT_BYTES", 3)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            return False

        def read(self, maximum):
            assert maximum == 4
            return b"abcd"

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    status, content, _, error = module.download("https://example.org/large")
    assert status is None and content == b""
    assert "limite" in error


def test_pdf_conversion_failure_is_not_silently_empty(monkeypatch):
    def failed_conversion(*args, **kwargs):
        assert kwargs["check"] is True
        raise subprocess.CalledProcessError(1, args[0], stderr=b"invalid PDF")

    monkeypatch.setattr(discourse_extraction.subprocess, "run", failed_conversion)
    with pytest.raises(subprocess.CalledProcessError):
        discourse_extraction.pages_of({"arquivo": "invalid.pdf"})
