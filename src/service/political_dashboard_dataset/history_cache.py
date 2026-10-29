"""Bounded immutable history versions; the database validates the version on every use."""

import json
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class HistoryCacheEntry:
    version: str
    serialized_rows: bytes

    def rows(self):
        return json.loads(self.serialized_rows)


class VersionedHistoryCache:
    def __init__(self, *, capacity=32, max_bytes=8 * 1024 * 1024):
        if capacity < 1 or max_bytes < 1:
            raise ValueError("History cache limits must be positive")
        self.capacity, self.max_bytes = capacity, max_bytes
        self._entries = OrderedDict()
        self._bytes = 0
        self._lock = RLock()
        self._load_locks = tuple(RLock() for _ in range(16))

    def lock_for(self, key):
        return self._load_locks[hash(key) % len(self._load_locks)]

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
            return entry

    def store(self, key, version, rows):
        serialized = json.dumps(rows, ensure_ascii=False, allow_nan=False).encode()
        if len(serialized) > self.max_bytes:
            return
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous:
                self._bytes -= len(previous.serialized_rows)
            while self._entries and (
                len(self._entries) >= self.capacity
                or self._bytes + len(serialized) > self.max_bytes
            ):
                self._bytes -= len(self._entries.popitem(last=False)[1].serialized_rows)
            self._entries[key] = HistoryCacheEntry(version, serialized)
            self._bytes += len(serialized)
