"""Bounded short-lived cache of public JSON search projections only."""

import json
from collections import OrderedDict
from threading import RLock
from time import monotonic


class PublicSearchCache:
    def __init__(self, *, ttl_seconds=30, capacity=128, max_bytes=2 * 1024 * 1024,
                 clock=monotonic):
        if ttl_seconds <= 0 or capacity < 1 or max_bytes < 1:
            raise ValueError("Cache limits must be positive")
        self.ttl_seconds, self.capacity, self.max_bytes = ttl_seconds, capacity, max_bytes
        self.clock = clock
        self._entries = OrderedDict()
        self._bytes = 0
        self._generation = 0
        self._lock = RLock()
        self._load_locks = tuple(RLock() for _ in range(16))

    def clear(self):
        with self._lock:
            self._generation += 1
            self._entries.clear()
            self._bytes = 0

    def get_or_load(self, key, load):
        # Identical keys share a loader; hits never wait for database I/O.
        with self._load_locks[hash(key) % len(self._load_locks)]:
            with self._lock:
                generation = self._generation
                self._expire()
                entry = self._entries.get(key)
                if entry is not None:
                    self._entries.move_to_end(key)
                    serialized = entry[1]
                else:
                    serialized = None
            if serialized is None:
                serialized = json.dumps(load(), ensure_ascii=False, allow_nan=False).encode()
                if len(serialized) <= self.max_bytes:
                    with self._lock:
                        if generation == self._generation:
                            self._store(key, serialized)
            return json.loads(serialized)

    def _expire(self):
        now = self.clock()
        for key in list(self._entries):
            if self._entries[key][0] <= now:
                self._bytes -= len(self._entries.pop(key)[1])

    def _store(self, key, serialized):
        while self._entries and (
            len(self._entries) >= self.capacity or self._bytes + len(serialized) > self.max_bytes
        ):
            self._bytes -= len(self._entries.popitem(last=False)[1][1])
        self._entries[key] = (self.clock() + self.ttl_seconds, serialized)
        self._bytes += len(serialized)
