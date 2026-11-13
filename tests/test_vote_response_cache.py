"""Vote response cache, catalog memo and parallel partition reads; fakes only, no network."""

import threading
import time
from datetime import date

import pytest

from service.dataset_storage import catalog as catalog_module
from service.dataset_storage.parallel import parallel_map
from service.public_profile.vote_response_cache import VoteResponseCache


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeReader:
    def __init__(self, clock):
        self.clock = clock
        self.catalog_memo = None
        self.catalog_lock = threading.Lock()


@pytest.fixture
def listing(monkeypatch):
    state = {"calls": 0, "partitions": [{"source": "camara", "occurred_on": "2026-10-14"}],
             "fail": False}

    def load(reader):
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("storage down")
        return list(state["partitions"])

    monkeypatch.setattr(catalog_module, "load_published_partitions", load)
    return state


def make(clock):
    reader = FakeReader(clock)
    return reader, VoteResponseCache(reader, ttl_seconds=60, capacity=2, clock=clock)


def test_hit_miss_and_isolated_copies():
    clock = Clock()
    _, cache = make(clock)
    calls = []

    def load():
        calls.append(1)
        return {"items": [1, 2]}

    first = cache.get_or_load("p1", {"limit": "30"}, date(2026, 11, 5), load)
    first["items"].append(99)  # callers cannot corrupt the cached value
    second = cache.get_or_load("p1", {"limit": "30"}, date(2026, 11, 5), load)
    assert second == {"items": [1, 2]} and len(calls) == 1
    cache.get_or_load("p2", {"limit": "30"}, date(2026, 11, 5), load)
    cache.get_or_load("p1", {"limit": "10"}, date(2026, 11, 5), load)
    cache.get_or_load("p1", {"limit": "30"}, date(2026, 11, 6), load)
    assert len(calls) == 4


def test_ttl_expiry_and_capacity():
    clock = Clock()
    _, cache = make(clock)
    calls = []
    load = lambda: calls.append(1) or {"n": len(calls)}  # noqa: E731
    cache.get_or_load("p", {}, "d", load)
    clock.now += 59
    cache.get_or_load("p", {}, "d", load)
    assert len(calls) == 1
    clock.now += 2
    cache.get_or_load("p", {}, "d", load)
    assert len(calls) == 2
    for person in ("a", "b", "c"):  # capacity 2 evicts the oldest
        cache.get_or_load(person, {}, "d", load)
    before = len(calls)
    cache.get_or_load("a", {}, "d", load)
    assert len(calls) == before + 1


def test_failures_are_not_cached():
    _, cache = make(Clock())
    attempts = []

    def load():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("DATASET_STORAGE_UNAVAILABLE")
        return {"ok": True}

    with pytest.raises(RuntimeError):
        cache.get_or_load("p", {}, "d", load)
    assert cache.get_or_load("p", {}, "d", load) == {"ok": True}
    cache.get_or_load("p", {}, "d", load)
    assert len(attempts) == 2


def test_new_dataset_version_invalidates_cached_response(listing):
    clock = Clock()
    reader, cache = make(clock)
    calls = []
    load = lambda: calls.append(1) or {"n": len(calls)}  # noqa: E731
    cache.get_or_load("p", {}, "d", load, warm_catalog=True)
    cache.get_or_load("p", {}, "d", load, warm_catalog=True)
    assert len(calls) == 1 and listing["calls"] == 1
    listing["partitions"].insert(0, {"source": "camara", "occurred_on": "2026-10-15"})
    clock.now += catalog_module.CATALOG_MEMORY_TTL_SECONDS + 1
    cache.get_or_load("p", {}, "d", load, warm_catalog=True)
    assert len(calls) == 2 and listing["calls"] == 2


def test_catalog_memo_ttl_and_failure_not_memoized(listing):
    clock = Clock()
    reader = FakeReader(clock)
    listing["fail"] = True
    with pytest.raises(RuntimeError):
        catalog_module.published_partitions(reader)
    listing["fail"] = False
    assert catalog_module.published_partitions(reader)[0]["occurred_on"] == "2026-10-14"
    catalog_module.published_partitions(reader)
    assert listing["calls"] == 2  # one failure + one success, then served from memory
    clock.now += catalog_module.CATALOG_MEMORY_TTL_SECONDS + 1
    catalog_module.published_partitions(reader)
    assert listing["calls"] == 3


def test_parallel_map_preserves_order_and_runs_concurrently():
    def slow(value):
        time.sleep(0.05 * (5 - value))  # later items finish first
        return value * 10

    started = time.monotonic()
    assert parallel_map(slow, [1, 2, 3, 4]) == [10, 20, 30, 40]
    assert time.monotonic() - started < 0.4  # serial would be 0.5 s


def test_parallel_map_failure_returns_nothing_and_respects_worker_limit():
    active, peak, lock = 0, 0, threading.Lock()

    def work(value):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        if value == 3:
            raise ValueError("boom")
        return value

    with pytest.raises(ValueError):
        parallel_map(work, range(12), max_workers=4)
    assert peak <= 4
    assert parallel_map(lambda v: v, [7]) == [7]
    assert parallel_map(lambda v: v, []) == []


def test_reader_created_after_cache_is_used_for_catalog_and_version(listing):
    """Serverless apps build the cache without a reader and create the Storage reader lazily."""
    clock = Clock()
    cache = VoteResponseCache(None, ttl_seconds=60, capacity=2, clock=clock)
    assert cache.get_or_load("p1", {}, date(2026, 11, 5), lambda: {"n": 1}, warm_catalog=True) == {
        "n": 1
    }
    assert listing["calls"] == 0  # no reader yet: nothing to warm, and no AttributeError

    late_reader = FakeReader(clock)
    cache.get_or_load(
        "p1", {}, date(2026, 11, 5), lambda: {"n": 2}, warm_catalog=True,
        dataset_reader=late_reader,
    )
    assert listing["calls"] == 1
    assert late_reader.catalog_memo is not None


def test_storage_catalog_failure_becomes_public_503_error(monkeypatch):
    from service.dataset_storage.read import DatasetReadError
    from service.public_profile.contracts import PublicProfileError

    def unavailable(reader):
        raise DatasetReadError("DATASET_CATALOG_UNAVAILABLE")

    monkeypatch.setattr(catalog_module, "load_published_partitions", unavailable)
    clock = Clock()
    _, cache = make(clock)
    with pytest.raises(PublicProfileError) as raised:
        cache.get_or_load("p1", {}, date(2026, 11, 5), lambda: {}, warm_catalog=True)
    assert (raised.value.code, raised.value.status_code) == ("DATASET_CATALOG_UNAVAILABLE", 503)
