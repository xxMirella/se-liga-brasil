"""Exercise the production WSGI contract without database or Storage access."""

import gzip
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

import pytest

from application.vercel import PublicPortalWSGI, ServerlessPortalApplication, create_dataset_reader


def request(application, path="/", **overrides):
    environ = {}
    setup_testing_defaults(environ)
    environ["QUERY_STRING"] = ""
    environ.update(PATH_INFO=path, **overrides)
    captured = []
    response = validator(application)(environ, lambda *args: captured.append(args))
    try:
        body = b"".join(response)
    finally:
        response.close()
    status, headers = captured[0]
    return int(status[:3]), dict(headers), body


def test_production_entrypoint_loads_without_credentials_or_local_server(monkeypatch):
    monkeypatch.setattr(
        "application.vercel.create_dataset_reader",
        lambda: pytest.fail("Static pages must not initialize Storage"),
    )
    root = Path(__file__).resolve().parents[1]
    specification = importlib.util.spec_from_file_location("production_app", root / "app.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    status, headers, body = request(module.app)
    assert status == 200
    assert b"Se Liga" in body
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_wsgi_preserves_query_parameters_and_dynamic_no_store():
    received = []
    portal = SimpleNamespace(fetch_people=lambda query: received.append(query) or {"items": []})
    status, headers, body = request(
        PublicPortalWSGI(portal), "/api/people", QUERY_STRING="q=Jo%C3%A3o&limit=8"
    )
    assert status == 200
    assert received == [{"q": "João", "limit": "8"}]
    assert headers["Cache-Control"] == "no-store"
    assert body == b'{"items": []}'


def test_static_compression_etag_and_head_follow_http_contract():
    application = PublicPortalWSGI()
    status, headers, body = request(application, HTTP_ACCEPT_ENCODING="gzip")
    assert status == 200
    assert b"Se Liga" in gzip.decompress(body)
    assert headers["Content-Encoding"] == "gzip"
    assert headers["Content-Length"] == str(len(body))
    status, cached_headers, body = request(
        application, HTTP_ACCEPT_ENCODING="gzip", HTTP_IF_NONE_MATCH=headers["ETag"]
    )
    assert status == 304
    assert body == b""
    assert "Content-Length" not in cached_headers
    status, head_headers, body = request(application, REQUEST_METHOD="HEAD")
    assert status == 200
    assert int(head_headers["Content-Length"]) > 0
    assert body == b""


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "OPTIONS"])
def test_mutating_methods_never_query_the_portal(method):
    status, headers, body = request(PublicPortalWSGI(object()), REQUEST_METHOD=method)
    assert status == 405
    assert headers["Allow"] == "GET, HEAD"
    assert headers["Cache-Control"] == "no-store"
    assert b"METHOD_NOT_ALLOWED" in body


def test_missing_storage_configuration_returns_503_without_leaking_details(monkeypatch):
    def unavailable():
        raise ValueError("secret-credential-detail")

    monkeypatch.setattr("application.vercel.create_dataset_reader", unavailable)
    person = "00000000-0000-0000-0000-000000000001"
    status, headers, body = request(PublicPortalWSGI(), f"/api/people/{person}/votes")
    assert status == 503
    assert headers["Cache-Control"] == "no-store"
    assert body == b'{"error": "TEMPORARILY_UNAVAILABLE"}'


def test_storage_reader_initializes_once_when_votes_are_requested(monkeypatch):
    readers = []
    reader = object()
    monkeypatch.setattr(
        "application.vercel.create_dataset_reader", lambda: readers.append(reader) or reader
    )
    monkeypatch.setattr(
        "application.vercel.PublicPortalApplication.fetch_votes", lambda *_: {"items": []}
    )
    application = ServerlessPortalApplication()
    assert application.fetch_votes("person", {}) == {"items": []}
    assert application.fetch_votes("person", {}) == {"items": []}
    assert readers == [reader]


def test_dataset_cache_uses_writable_temporary_directory(monkeypatch, tmp_path):
    monkeypatch.setattr("application.vercel.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        "service.dataset_storage.supabase.load_storage_configuration", lambda: object()
    )
    reader = create_dataset_reader()
    try:
        assert reader.directory == tmp_path / "se-liga-brasil-public-cache"
        assert reader.directory.is_dir()
    finally:
        reader.storage.client.close()
