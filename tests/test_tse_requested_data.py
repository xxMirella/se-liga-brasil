"""Target scope must use personal evidence, never a provider sequence as identity."""

from crawlers.tse.requested_data import RequestedTseConfiguration


def configuration(tmp_path):
    return RequestedTseConfiguration(
        storage_directory=tmp_path,
        document_fingerprints=frozenset({"known-document"}),
        name_birth_pairs=frozenset({("PESSOA FICTICIA", "1980-01-01")}),
    )


def record(document=None, name="PESSOA FICTICIA", birth="1980-01-01"):
    return {
        "identityEvidence": {"documentFingerprint": document, "normalizedName": name},
        "normalizedData": {"birthDate": birth, "candidateSequence": "arbitrary"},
    }


def test_requested_scope_accepts_document_even_when_birth_is_missing(tmp_path):
    assert configuration(tmp_path).allows_identity(record("known-document", birth=None))


def test_unknown_document_cannot_fall_back_to_name_and_birth(tmp_path):
    assert not configuration(tmp_path).allows_identity(record("other-document"))


def test_name_without_birth_is_not_identity(tmp_path):
    assert not configuration(tmp_path).allows_identity(record(birth=None))


def test_unique_full_name_birth_fallback(tmp_path):
    assert configuration(tmp_path).allows_identity(record())


def test_new_document_can_enrich_unique_documentless_person(tmp_path):
    from dataclasses import replace

    scope = replace(configuration(tmp_path), documentless_name_birth_pairs=frozenset({
        ("PESSOA FICTICIA", "1980-01-01"),
    }))
    assert scope.allows_identity(record("new-document"))
    assert not scope.allows_identity(record("new-document", birth="1981-01-01"))
    conflicting = replace(scope, conflicting_document_fingerprints=frozenset({"other"}))
    assert not conflicting.allows_identity(record("other"))


def test_database_scope_only_enables_new_documents_for_unique_unidentified_people(tmp_path):
    from unittest.mock import Mock

    from crawlers.tse.requested_data import load_requested_personal_scope

    connection = Mock()
    connection.execute.return_value.fetchall.side_effect = [
        [
            {"normalized_name": "PESSOA FICTICIA", "birth_date": "1980-01-01",
             "document_fingerprint": None, "unique_name_birth": True},
            {"normalized_name": "HOMONIMO", "birth_date": "1980-01-01",
             "document_fingerprint": None, "unique_name_birth": False},
            {"normalized_name": "DOCUMENTADO", "birth_date": "1980-01-01",
             "document_fingerprint": "known-document", "unique_name_birth": True},
        ],
        [{"document_fingerprint": "foreign-document"}],
    ]
    scope = RequestedTseConfiguration(
        storage_directory=tmp_path, **load_requested_personal_scope(connection, ["person"])
    )
    assert scope.allows_identity(record("new-document"))
    assert not scope.allows_identity(record("foreign-document"))
    assert not scope.allows_identity(record("new-document", name="HOMONIMO"))
    assert not scope.allows_identity(record("new-document", name="DOCUMENTADO"))


def test_acquisition_groups_missing_kinds_without_reloading_existing(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from crawlers.tse import enrichment

    existing = SimpleNamespace(resource=SimpleNamespace(year=2026, kind="candidate"))
    asset = SimpleNamespace(year=2026, kind="asset")
    candidate = SimpleNamespace(year=2026, kind="candidate")
    acquired = []
    monkeypatch.setattr(enrichment, "load_selected_downloads", lambda *_: [existing])
    monkeypatch.setattr(enrichment, "discover_resources", lambda *_: [candidate, asset])

    def download(configuration, client, resources):
        acquired.extend(resources)
        return [SimpleNamespace(resource=resource) for resource in resources], []

    monkeypatch.setattr(enrichment, "download_selected_resources", download)
    scope = RequestedTseConfiguration(
        storage_directory=tmp_path, years=(2026,), kinds=("candidate", "asset")
    )
    downloads, failures = enrichment.acquire_asset_backfill(scope, object())
    assert acquired == [asset]
    assert len(downloads) == 2
    assert failures == []
