"""Polite, resumable download of official files with a hash manifest.

Responsibility: fetch one URL at a time, pause between requests, retry transient failures,
record url/year/sha256/bytes/downloaded_at in ``manifest.json`` and keep the original bytes
only below a size limit. Larger files are hashed while streaming and handed to a processor.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from storage.files import write_private_bytes

USER_AGENT = "se-liga-brasil-research/0.1 (open-data research; mirella.mih1006@gmail.com)"
RETAIN_LIMIT_BYTES = 50 * 1024 * 1024
PAUSE_SECONDS = 1.0
MAX_ATTEMPTS = 4


@dataclass(frozen=True)
class FetchedFile:
    url: str
    path: Path
    sha256: str
    bytes: int
    retained: bool


class PoliteArchive:
    def __init__(
        self, directory: Path, pause_seconds: float = PAUSE_SECONDS, manifest_name="manifest.json"
    ) -> None:
        self.directory = directory
        self.pause_seconds = pause_seconds
        self.manifest_path = directory / manifest_name
        self.entries = self._load_manifest()
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=httpx.Timeout(120.0), follow_redirects=True
        )

    def close(self) -> None:
        self.client.close()

    def _load_manifest(self) -> dict[str, dict]:
        if not self.manifest_path.exists():
            return {}
        document = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {entry["arquivo"]: entry for entry in document["arquivos"]}

    def _save_manifest(self) -> None:
        ordered = sorted(self.entries.values(), key=lambda entry: entry["arquivo"])
        payload = json.dumps({"arquivos": ordered}, ensure_ascii=False, indent=1).encode("utf-8")
        write_private_bytes(self.manifest_path, [payload])

    def retained_copy(self, relative_name: str) -> Path | None:
        """Return the stored original when it exists and still matches the manifest."""
        entry = self.entries.get(relative_name)
        path = self.directory / relative_name
        if (
            entry
            and entry.get("retained")
            and path.exists()
            and path.stat().st_size == entry["bytes"]
        ):
            return path
        return None

    def fetch(self, url: str, relative_name: str, year: int, kind: str, params=None) -> FetchedFile:
        """Download ``url``; reuse the retained original when the manifest vouches for it."""
        cached = self.retained_copy(relative_name)
        if cached:
            entry = self.entries[relative_name]
            return FetchedFile(url, cached, entry["sha256"], entry["bytes"], True)
        destination = self.directory / relative_name
        fetched = self._download_with_retry(url, destination, params)
        self._record(relative_name, fetched, year, kind, params)
        return fetched

    def release(self, relative_name: str) -> None:
        """After processing, drop the bytes of files above the size limit; keep url + hash."""
        entry = self.entries.get(relative_name)
        if entry and entry["bytes"] > RETAIN_LIMIT_BYTES and entry["retained"]:
            (self.directory / relative_name).unlink(missing_ok=True)
            entry["retained"] = False
            self._save_manifest()

    def is_processed_large_file(self, relative_name: str) -> bool:
        entry = self.entries.get(relative_name)
        return bool(entry and not entry["retained"] and entry["bytes"] > RETAIN_LIMIT_BYTES)

    def record_unavailable(self, url: str, relative_name: str, year: int, kind: str, status: int):
        self.entries[relative_name] = {
            "arquivo": relative_name,
            "url": url,
            "ano": year,
            "tipo": kind,
            "http_status": status,
            "retained": False,
            "bytes": 0,
            "sha256": None,
            "baixado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self._save_manifest()

    def is_known_unavailable(self, relative_name: str) -> bool:
        return "http_status" in self.entries.get(relative_name, {})

    def _record(self, name, fetched: FetchedFile, year: int, kind: str, params) -> None:
        self.entries[name] = {
            "arquivo": name,
            "url": fetched.url,
            "parametros": params or {},
            "ano": year,
            "tipo": kind,
            "sha256": fetched.sha256,
            "bytes": fetched.bytes,
            "retained": fetched.retained,
            "baixado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self._save_manifest()

    def _download_with_retry(self, url, destination: Path, params) -> FetchedFile:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            time.sleep(self.pause_seconds * attempt)
            try:
                return self._download_once(url, destination, params)
            except (httpx.HTTPError, OSError):
                if attempt == MAX_ATTEMPTS:
                    raise
        raise RuntimeError("unreachable")

    def _download_once(self, url, destination: Path, params) -> FetchedFile:
        digest, size = hashlib.sha256(), 0

        def chunks():
            nonlocal size
            with self.client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    yield chunk

        write_private_bytes(destination, chunks())
        return FetchedFile(
            str(httpx.URL(url, params=params)), destination, digest.hexdigest(), size, True
        )
