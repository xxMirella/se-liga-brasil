"""Photos retain the verified personal bridge and official source provenance."""

import json

import pytest

from crawlers.alesp.photos import cached_photo_records, normalize_profile_photo


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "//evil.test/a.jpg",
        "https://evil.test/a.jpg",
        "https://www3.al.sp.gov.br:444/a.jpg",
        "http://www3.al.sp.gov.br/a.jpg",
    ],
)
def test_photo_rejects_untrusted_links(value):
    assert normalize_profile_photo(value) is None


def test_photo_uses_same_relative_path_rule_as_official_portal():
    assert normalize_profile_photo("/biografia/fotos/example.png") == (
        "https://www3.al.sp.gov.br/legis/biografia/fotos/example.png"
    )


def test_cached_photos_only_link_verified_requested_people(tmp_path):
    profile = tmp_path / "original.json"
    payload = json.dumps(
        {
            "idParlamentar": 42,
            "nuMatricula": 100,
            "biografia": {"txFotoGrande": "/biografia/fotos/example.png"},
        }
    )
    profile.write_text(payload)
    resolution = {
        "person_id": "person-one",
        "status": "matched",
        "official_subjects": [
            {
                "source_subject_id": "42",
                "matricula": "100",
                "sources": [
                    {
                        "evidence_kind": "profile",
                        "path": str(profile),
                        "url": "https://www.al.sp.gov.br/profile",
                        "sha256": "verified-checksum",
                        "fetched_at": "2026-10-17T00:00:00Z",
                    }
                ],
            }
        ],
    }
    records = list(cached_photo_records([resolution], {"person-one"}))
    assert len(records) == 1
    assert records[0]["personId"] == "person-one"
    assert records[0]["photoUrl"].startswith("https://www3.al.sp.gov.br/legis/")
    assert records[0]["evidence"][0]["sha256"] == "verified-checksum"
    assert list(cached_photo_records([resolution], {"another-person"})) == []
    assert list(cached_photo_records([resolution | {"status": "ambiguous"}], None)) == []
    assert profile.read_text() == payload


@pytest.mark.parametrize(
    "profile",
    [
        {"idParlamentar": 99, "nuMatricula": 100},
        {"idParlamentar": 42, "nuMatricula": 999},
        {"idParlamentar": 42, "nuMatricula": 100, "biografia": ["invalid"]},
    ],
)
def test_cached_photo_rejects_mismatched_or_changed_profile(tmp_path, profile):
    from crawlers.alesp.photos import cached_subject_photo
    from service.ingestion.contracts import IngestionError

    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile))
    subject = {
        "source_subject_id": "42",
        "matricula": "100",
        "sources": [{"evidence_kind": "profile", "path": str(path)}],
    }
    with pytest.raises(IngestionError):
        cached_subject_photo(subject)


def test_cached_photo_missing_or_unpublished_is_not_invented():
    from crawlers.alesp.photos import cached_subject_photo

    assert cached_subject_photo({"sources": [{"evidence_kind": "telephone"}]}) is None
    assert (
        list(cached_photo_records([{"status": "matched", "official_subjects": [{}]}], None)) == []
    )


def test_shared_original_checksum_is_read_once_per_path_and_hash(tmp_path, monkeypatch):
    from crawlers.alesp import local_enrichment

    calls = []
    monkeypatch.setattr(local_enrichment, "hash_file", lambda path: calls.append(path) or "sha")
    source = {"path": str(tmp_path / "original.xml"), "sha256": "sha"}
    resolution = {"official_subjects": [{"sources": [source, source]}]}
    assert local_enrichment.verified_evidence_references([resolution, resolution]) == [source]
    assert calls == [tmp_path / "original.xml"]
