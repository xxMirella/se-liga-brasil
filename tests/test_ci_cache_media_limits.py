"""Cache negotiation and local photo evidence must fail closed on corrupt inputs."""

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application.public_cache import accepts_gzip, prepare_public_response, public_cache_policy
from service.acquisition import rate_limit
from service.profile_media import backfill


@pytest.mark.parametrize(
    "header,accepted",
    [
        ("br, gzip;q=invalid", False),
        ("gzip;q=0", False),
        ("gzip;q=2", False),
        ("gzip;q=-1", False),
        ("br, gzip;q=0.5", True),
        ("identity", False),
    ],
)
def test_compression_requires_a_valid_positive_quality(header, accepted):
    assert accepts_gzip(header) is accepted


def test_cache_does_not_store_errors_and_gzip_etag_revalidates():
    assert public_cache_policy("/como-funciona", 503) == "no-store"
    first = prepare_public_response("/como-funciona", 200, b"a" * 2048, {"Accept-Encoding": "gzip"})
    assert first[2]["Content-Encoding"] == "gzip"
    second = prepare_public_response(
        "/como-funciona",
        200,
        b"a" * 2048,
        {
            "Accept-Encoding": "gzip",
            "If-None-Match": first[2]["ETag"],
        },
    )
    assert second[0] == 304 and second[1] == b""


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Thu, 01 Jan 2026 00:01:00 GMT", 60),
        ("bad date", 0),
        ("Thu, 01 Jan 2025 00:00:00 GMT", 0),
        (None, 0),
    ],
)
def test_retry_after_http_dates_are_bounded_below_zero(value, expected):
    assert rate_limit.retry_after_seconds(value, datetime(2026, 1, 1, tzinfo=UTC)) == expected


@pytest.mark.parametrize("limit", [0, 10001])
def test_photo_backfill_rejects_unbounded_requests_before_reading(limit, tmp_path):
    with pytest.raises(ValueError, match="INVALID_PROFILE_LIMIT"):
        backfill.backfill_profile_photos(None, tmp_path, limit=limit)


@pytest.mark.parametrize("corruption", ["unrelated", "outside", "digest", "malformed", "valid"])
def test_local_photo_evidence_requires_containment_and_checksum(tmp_path, corruption):
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    payload = {
        "DetalheParlamentar": {
            "Parlamentar": {"IdentificacaoParlamentar": {"NomeCompletoParlamentar": "Pessoa"}}
        }
    }
    raw = json.dumps(payload).encode()
    path = tmp_path / "source.json"
    path.write_bytes(raw)
    manifest = {
        "source_url": "https://legis.senado.leg.br/dadosabertos/senador/1",
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if corruption == "unrelated":
        manifest["source_url"] = "https://unrelated.invalid"
    if corruption == "outside":
        manifest["path"] = str(tmp_path.parent / "outside-photo.json")
    if corruption == "digest":
        manifest["sha256"] = "0" * 64
    target = manifests / "senado-profile.json"
    target.write_text("{" if corruption == "malformed" else json.dumps(manifest))
    result = backfill.load_local_senate_photos(
        tmp_path, {"https://legis.senado.leg.br/dadosabertos/senador/1"}
    )
    assert bool(result) == (corruption == "valid")


def test_photo_backfill_keeps_valid_current_photo_and_reports_missing_evidence(tmp_path):
    rows = [
        {
            "person_id": "one",
            "source_code": "camara",
            "source_url": "https://www.camara.leg.br/1",
            "photo_url": "https://www.camara.leg.br/photo.jpg",
            "profile": {},
        },
        {
            "person_id": "two",
            "source_code": "camara",
            "source_url": "https://www.camara.leg.br/2",
            "photo_url": None,
            "profile": {},
        },
    ]
    repository = SimpleNamespace(fetch_linked_profiles=lambda _: rows, save_official_photos=Mock())
    report = backfill.backfill_profile_photos(repository, tmp_path, apply=True)
    assert report["missing_valid_photo_evidence"] == {"camara": 1}
    assert report["proposed_people"] == 0
    repository.save_official_photos.assert_not_called()


def test_photo_legacy_raw_cannot_match_different_civil_name():
    row = {
        "source_code": "senado",
        "source_url": "source",
        "profile": {"civilName": "Pessoa A", "birthDate": "1980-01-01"},
    }
    raw = {
        "source": {
            "IdentificacaoParlamentar": {
                "NomeCompletoParlamentar": "Pessoa B",
                "UrlFotoParlamentar": "https://www.senado.leg.br/photo.jpg",
            },
            "DadosBasicosParlamentar": {"DataNascimento": "1980-01-01"},
        }
    }
    assert backfill.resolve_profile_photo(row, raw) is None
