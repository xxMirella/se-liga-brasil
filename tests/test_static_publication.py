import gzip
import json
from pathlib import Path

import pytest

from application.public_cache import prepare_public_response
from service.static_publication.build import build_civic_site


def test_export_is_deterministic_and_all_filters_are_static(tmp_path):
    output = tmp_path / "site"
    build_civic_site(output, backend_origin="https://api.example.org")
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    build_civic_site(output, backend_origin="https://api.example.org")
    assert before == {
        p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }
    manifest = json.loads((output / "manifest.json").read_text())
    assert len(manifest["files"]) == 11
    for sphere in ("municipal", "estadual", "federal", "distrital", "todos"):
        path = output / "como-funciona" / sphere / "index.html"
        document = path.read_text()
        assert "?esfera=" not in document
        assert 'href="/como-funciona/federal/#cargos"' in document
        assert 'action="https://api.example.org/pessoas"' in document
        assert gzip.decompress(Path(str(path) + ".gz").read_bytes()) == path.read_bytes()
        for stylesheet in output.glob("assets/*.css"):
            assert "/assets/" + stylesheet.name in document
    assert "immutable" in (output / "_headers").read_text()
    assert "form-action 'self' https://api.example.org" in (output / "_headers").read_text()


@pytest.mark.parametrize("origin", ["http://example.org", "https://u:p@example.org", "https://x/y"])
def test_static_export_rejects_unsafe_backend_origins(tmp_path, origin):
    with pytest.raises(ValueError):
        build_civic_site(tmp_path, backend_origin=origin)
    assert not list(tmp_path.iterdir())


def test_cache_compression_validation_and_private_routes():
    body = b"public content " * 200
    status, encoded, headers = prepare_public_response(
        "/como-funciona?esfera=todos", 200, body, {"Accept-Encoding": "gzip"}
    )
    assert status == 200
    assert gzip.decompress(encoded) == body
    assert headers["Content-Encoding"] == "gzip"
    assert headers["Vary"] == "Accept-Encoding"
    assert "public" in headers["Cache-Control"]
    status, empty, _ = prepare_public_response(
        "/como-funciona",
        200,
        body,
        {"Accept-Encoding": "gzip", "If-None-Match": "W/" + headers["ETag"]},
    )
    assert (status, empty) == (304, b"")
    _, identity, identity_headers = prepare_public_response(
        "/como-funciona", 200, body, {"Accept-Encoding": "gzip;q=0"}
    )
    assert identity == body
    assert identity_headers["ETag"] != headers["ETag"]
    for route, status in (("/pessoas", 200), ("/api/people", 200), ("/como-funciona", 400)):
        assert prepare_public_response(route, status, body, {})[2] == {"Cache-Control": "no-store"}
