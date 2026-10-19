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
