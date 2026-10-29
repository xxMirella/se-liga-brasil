"""Disk cache of generated answers, so the same request is never paid for twice."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def request_cache_key(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode() + b"\0")
    return digest.hexdigest()


class DiskResponseCache:
    def __init__(self, directory: Path):
        self._directory = directory

    def _path(self, key: str) -> Path:
        return self._directory / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return json.loads(path.read_text())

    def put(self, key: str, payload: dict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(handle, "w") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        os.replace(temporary, path)
