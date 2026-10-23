"""Publish content-addressed datasets before activating their private remote manifest."""

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit

from dotenv import dotenv_values

from service.analytical_datasets.storage import file_sha256

MAX_OBJECT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class StorageConfiguration:
    url: str
    key: str = field(repr=False)
    bucket: str = "voting-datasets"

    def __post_init__(self):
        parsed = urlsplit(self.url)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".supabase.co"):
            raise ValueError("Expected an official Supabase Storage HTTPS endpoint")
        if parsed.username or parsed.password or parsed.port or parsed.path not in {"", "/"}:
            raise ValueError("Invalid Supabase Storage endpoint")
        if not self.key or not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", self.bucket):
            raise ValueError("A storage key and valid bucket are required")


def load_storage_configuration(env_file=None):
    values = dict(dotenv_values(Path(__file__).resolve().parents[3] / ".env.storage"))
    if env_file:
        values.update(dotenv_values(env_file))
    values.update(os.environ)
    return storage_configuration_from_values(values)


def storage_configuration_from_values(values):
    url = values.get("SUPABASE_STORAGE_URL") or values.get("SUPABASE_URL", "")
    if not url.startswith("https://"):
        project = values.get("SUPABASE_PROJECT_ID", "")
        url = f"https://{project}.supabase.co" if re.fullmatch(r"[a-z0-9]{20}", project) else ""
    key = values.get("SUPABASE_STORAGE_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_STORAGE_CREDENTIALS_REQUIRED")
    return StorageConfiguration(url.rstrip("/"), key)


class SupabaseDatasetStorage:
    def __init__(self, configuration, client):
        self.configuration, self.client = configuration, client

    def request(self, method, path, **arguments):
        return self.client.request(
            method,
            self.configuration.url + "/storage/v1/" + path,
            headers={
                "apikey": self.configuration.key,
                "Authorization": "Bearer " + self.configuration.key,
                **arguments.pop("headers", {}),
            },
            **arguments,
        )

    def ensure_private_bucket(self):
        response = self.request("GET", "bucket/" + self.configuration.bucket)
        missing = response.status_code == 404 or (
            response.status_code == 400 and response.json().get("code") == "NoSuchBucket"
        )
        if missing:
            response = self.request(
                "POST",
                "bucket",
                json={
                    "id": self.configuration.bucket,
                    "name": self.configuration.bucket,
                    "public": False,
                    "file_size_limit": MAX_OBJECT_BYTES,
                },
            )
            response.raise_for_status()
            return
        response.raise_for_status()
        if response.json().get("public") is not False:
            raise ValueError("Dataset publication requires a private bucket")

    def upload_immutable(self, object_key, local_path, expected_sha256):
        if (
            local_path.stat().st_size > MAX_OBJECT_BYTES
            or file_sha256(local_path) != expected_sha256
        ):
            raise ValueError("Storage object exceeds budget or differs from manifest")
        path = self.object_path(object_key)
        with local_path.open("rb") as content:
            response = self.request(
                "POST",
                path,
                content=content,
                headers={"Content-Type": "application/octet-stream", "x-upsert": "false"},
            )
        if response.status_code in {400, 409}:
            self.verify_remote_object(path, expected_sha256)
        else:
            response.raise_for_status()

    def verify_remote_object(self, path, expected_sha256):
        digest, size = hashlib.sha256(), 0
        request = self.client.build_request(
            "GET",
            self.configuration.url + "/storage/v1/" + path,
            headers={
                "apikey": self.configuration.key,
                "Authorization": "Bearer " + self.configuration.key,
            },
        )
        response = self.client.send(request, stream=True)
        try:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_OBJECT_BYTES:
                    raise ValueError("Remote object exceeds verification budget")
                digest.update(chunk)
        finally:
            response.close()
        if digest.hexdigest() != expected_sha256:
            raise ValueError("Remote content-addressed object differs")

    def object_path(self, object_key):
        path = PurePosixPath(object_key)
        if path.is_absolute() or ".." in path.parts or str(path) != object_key:
            raise ValueError("Invalid dataset object key")
        return "object/" + self.configuration.bucket + "/" + quote(object_key, safe="/=")

    def publish_daily_manifest(self, directory, relative_path, manifest):
        self.ensure_private_bucket()
        self.upload_immutable(
            relative_path + "/" + manifest.parquet_file,
            directory / manifest.parquet_file,
            manifest.parquet_sha256,
        )
        self.upload_immutable(
            relative_path + "/" + manifest.private_state_file,
            directory / manifest.private_state_file,
            manifest.private_state_sha256,
        )
        body = json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":")).encode()
        response = self.request(
            "POST",
            self.object_path(relative_path + "/manifest.json"),
            content=body,
            headers={"Content-Type": "application/json", "x-upsert": "true"},
        )
        response.raise_for_status()
        return {
            "published": True,
            "row_count": manifest.row_count,
            "parquet_sha256": manifest.parquet_sha256,
        }
