from types import SimpleNamespace

import httpx
import pytest

from service.acquisition import http_client, rate_limit
from service.ingestion.contracts import IngestionError


def test_host_pacing_deduplicates_request_slots_without_real_sleep(monkeypatch):
    sleeps = []
    rate_limit.NEXT_REQUEST_AT.clear()
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 0)
    monkeypatch.setattr(rate_limit.time, "sleep", sleeps.append)
    rate_limit.pace_official_request("https://official.example/a")
    rate_limit.pace_official_request("https://official.example/b")
    rate_limit.pace_official_request("https://other.example/a")
    assert sleeps == [1.0]
    rate_limit.NEXT_REQUEST_AT.clear()


def test_long_retry_after_returns_to_orchestrator_without_early_retry(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "120"})

    monkeypatch.setattr(http_client, "pace_official_request", lambda *args: None)
    configuration = SimpleNamespace(max_attempts=3)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        source = http_client.OfficialHttpClient(
            configuration, client, frozenset({"official.example"})
        )
        with pytest.raises(IngestionError) as failure:
            source.fetch_bytes("https://official.example/a")
    assert len(calls) == 1
    assert failure.value.details["retry_after_seconds"] == 120


def test_blocked_host_is_not_hit_again_for_other_resources(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "120"})

    monkeypatch.setattr(http_client, "pace_official_request", lambda *args: None)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        source = http_client.OfficialHttpClient(
            SimpleNamespace(max_attempts=3), client, frozenset({"official.example"})
        )
        for path in ("a", "b"):
            with pytest.raises(IngestionError):
                source.fetch_bytes("https://official.example/" + path)
    assert len(calls) == 1
