"""Shared identity evidence must produce only one acquisition per URL."""

import json

from crawlers.alesp import reviewed_identity


def test_collect_acquires_shared_evidence_once(monkeypatch):
    profile_url = reviewed_identity.PROFILE_BASE_URL + "123"
    shared_url = "https://www.al.sp.gov.br/noticia/shared"
    case = {"matricula": "123", "evidence_urls": [profile_url, shared_url, shared_url]}
    registry = {
        "status": "reviewed_against_official_sources",
        "birth_date_changes_allowed": False,
        "exceptions": [case, case],
        "reviewed_on": "2026-10-16",
        "scope": {"state": "SP"},
    }
    calls = []

    def acquire(resource, configuration, client, budget):
        calls.append(resource.url)
        return json.dumps({}).encode(), {"url": resource.url}

    monkeypatch.setattr(reviewed_identity, "load_json", lambda path: registry)
    monkeypatch.setattr(reviewed_identity, "validate_reviewed_profile", lambda *args: None)
    monkeypatch.setattr(reviewed_identity, "acquire_identity_resource", acquire)
    results = reviewed_identity.collect_reviewed_identities(None, None)
    assert calls == [profile_url, shared_url]
    assert len(results) == 2
    assert results[0]["sources"] == [{"url": profile_url}, {"url": shared_url}]
