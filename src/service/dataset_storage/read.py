"""Bounded authenticated reads; only public projections enter the API cache."""

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from service.analytical_datasets.storage import file_sha256, validate_manifest
from service.daily_voting_dataset.contracts import DailyDatasetManifest
from service.dataset_storage.supabase import MAX_OBJECT_BYTES

MAX_MANIFEST_BYTES = 16 * 1024
MAX_CACHE_BYTES = 256 * 1024 * 1024
MANIFEST_TTL_SECONDS = 300
SNAPSHOT_TTL_SECONDS = 3600


class DatasetReadError(ValueError):
    def __init__(self, code, status_code=503):
        self.code, self.status_code = code, status_code
        super().__init__(code)


class DailyDatasetReader:
    def __init__(
        self, storage, cache_directory, *, max_cache_bytes=MAX_CACHE_BYTES, clock=time.time
    ):
        self.storage = storage
        self.directory = Path(cache_directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_cache_bytes = max_cache_bytes
        self.clock = clock
        self.lock = threading.RLock()

    def download(self, object_key, max_bytes, *, allow_missing=False):
        path = self.storage.object_path(object_key)
        configuration = self.storage.configuration
        request = self.storage.client.build_request(
            "GET",
            configuration.url + "/storage/v1/" + path,
            headers={"apikey": configuration.key, "Authorization": "Bearer " + configuration.key},
        )
        response = self.storage.client.send(request, stream=True)
        try:
            if response.status_code == 404 and allow_missing:
                return None
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise DatasetReadError("DATASET_OBJECT_TOO_LARGE")
                chunks.append(chunk)
            content = b"".join(chunks)
            if response.status_code == 400 and allow_missing:
                try:
                    if json.loads(content).get("code") == "NoSuchKey":
                        return None
                except (ValueError, AttributeError):
                    pass
            if response.status_code >= 400:
                raise DatasetReadError("DATASET_STORAGE_UNAVAILABLE")
            return content
        finally:
            response.close()

    def save_bytes(self, path, content):
        used = sum(item.stat().st_size for item in self.directory.rglob("*") if item.is_file())
        replaced = path.stat().st_size if path.exists() else 0
        if used - replaced + len(content) > self.max_cache_bytes:
            raise DatasetReadError("DATASET_CACHE_BUDGET_EXCEEDED")
        with NamedTemporaryFile(dir=self.directory, delete=False) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        try:
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def current_manifest(self, partition):
        key = partition.relative_path + "/manifest.json"
        cache_key = hashlib.sha256(key.encode()).hexdigest()
        path = self.directory / (cache_key + ".manifest.json")
        cached = read_cache_json(path) if path.exists() else None
        if cached and self.clock() - cached["checked_at"] < MANIFEST_TTL_SECONDS:
            return validate_daily_manifest(cached["manifest"], partition)
        body = self.download(key, MAX_MANIFEST_BYTES, allow_missing=True)
        try:
            manifest = validate_daily_manifest(json.loads(body) if body else None, partition)
        except ValueError as error:
            raise DatasetReadError("DATASET_MANIFEST_INVALID") from error
        self.save_bytes(
            path, json.dumps({"checked_at": self.clock(), "manifest": manifest}).encode()
        )
        return manifest

    def parquet_path(self, partition, manifest):
        digest = manifest["parquet_sha256"]
        path = self.directory / (digest + ".parquet")
        if path.exists():
            if file_sha256(path) != digest:
                raise DatasetReadError("DATASET_CACHE_INTEGRITY_FAILED")
            return path
        content = self.download(
            partition.relative_path + "/" + manifest["parquet_file"], MAX_OBJECT_BYTES
        )
        if hashlib.sha256(content).hexdigest() != digest:
            raise DatasetReadError("DATASET_OBJECT_INTEGRITY_FAILED")
        self.save_bytes(path, content)
        return path

    def create_snapshot(self, partitions, fingerprint, exercise_context=None):
        self.prune_expired_cache()
        entries = []
        for partition in partitions:
            manifest = self.current_manifest(partition)
            if manifest is not None:
                self.parquet_path(partition, manifest)
                entries.append({"manifest": manifest, "source": partition.institution_code})
        payload = {
            "created_at": self.clock(),
            "filters": fingerprint,
            "entries": entries,
            "exercise_context": exercise_context or [],
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        token = hashlib.sha256(content).hexdigest()
        self.save_bytes(self.directory / (token + ".snapshot.json"), content)
        return token, payload

    def prune_expired_cache(self):
        retained_hashes = set()
        for path in self.directory.glob("*.snapshot.json"):
            payload = read_cache_json(path)
            if self.clock() - payload["created_at"] >= SNAPSHOT_TTL_SECONDS:
                path.unlink()
            else:
                retained_hashes.update(
                    entry["manifest"]["parquet_sha256"] for entry in payload["entries"]
                )
        for path in self.directory.glob("*.manifest.json"):
            payload = read_cache_json(path)
            if self.clock() - payload["checked_at"] >= MANIFEST_TTL_SECONDS:
                path.unlink()
            elif payload["manifest"] is not None:
                retained_hashes.add(payload["manifest"]["parquet_sha256"])
        for path in self.directory.glob("*.parquet"):
            if path.stem not in retained_hashes:
                path.unlink()

    def load_snapshot(self, token, fingerprint):
        path = self.directory / (token + ".snapshot.json")
        if not path.exists():
            raise DatasetReadError("DATASET_SNAPSHOT_EXPIRED", 410)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != token:
            raise DatasetReadError("DATASET_SNAPSHOT_INTEGRITY_FAILED")
        payload = json.loads(content)
        if payload["filters"] != fingerprint:
            raise DatasetReadError("INVALID_CURSOR", 400)
        if self.clock() - payload["created_at"] >= SNAPSHOT_TTL_SECONDS:
            raise DatasetReadError("DATASET_SNAPSHOT_EXPIRED", 410)
        return payload


def validate_daily_manifest(payload, partition):
    if payload is None:
        return None
    try:
        manifest = DailyDatasetManifest(**payload)
        validate_manifest(manifest)
        if manifest.schema_version != "person_voting_timeline.v1":
            raise ValueError("Unsupported schema")
        if (manifest.institution_code, manifest.occurred_on, manifest.year) != (
            partition.institution_code,
            str(partition.occurred_on),
            partition.occurred_on.year,
        ):
            raise ValueError("Wrong daily partition")
        if not isinstance(manifest.parser_version, str) or not manifest.parser_version:
            raise ValueError("Missing parser version")
    except (TypeError, ValueError) as error:
        raise DatasetReadError("DATASET_MANIFEST_INVALID") from error
    return payload


def read_cache_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise DatasetReadError("DATASET_CACHE_INTEGRITY_FAILED") from error
