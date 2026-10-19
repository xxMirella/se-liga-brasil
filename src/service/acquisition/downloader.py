"""Stream downloads into immutable archives and maintain HTTP validators."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, DownloadedArtifact, IngestionError, Resource
from storage.files import create_private_directory, hash_file, load_json, save_json

ProgressCallback = Callable[[int, int | None], None]


def is_cached_archive_intact(manifest: dict | None, resource: Resource) -> bool:
    if not manifest or manifest["source_url"] != resource.url:
        return False
    path = Path(manifest["path"])
    return path.is_file() and hash_file(path) == manifest["sha256"]


def is_recently_checked(manifest: dict, configuration) -> bool:
    checked_at = datetime.fromisoformat(manifest.get("checked_at", manifest["last_full_check_at"]))
    age = datetime.now(UTC) - checked_at
    return timedelta(0) <= age < timedelta(hours=configuration.force_recheck_after_hours)


def build_downloaded_artifact(resource, manifest, acquisition_status) -> DownloadedArtifact:
    return DownloadedArtifact(
        resource,
        Path(manifest["path"]),
        manifest["sha256"],
        manifest["fetched_at"],
        manifest["bytes"],
        acquisition_status,
    )


def build_conditional_headers(manifest: dict | None, configuration) -> dict:
    if not manifest:
        return {}
    full_check = datetime.fromisoformat(manifest["last_full_check_at"])
    if datetime.now(UTC) - full_check >= timedelta(hours=configuration.force_recheck_after_hours):
        return {}
    headers = {}
    if manifest.get("etag"):
        headers["If-None-Match"] = manifest["etag"]
    if manifest.get("last_modified"):
        headers["If-Modified-Since"] = manifest["last_modified"]
    return headers


def enforce_download_limit(byte_count: int, budget: DownloadBudget, configuration) -> None:
    if byte_count > configuration.max_download_bytes:
        raise IngestionError("RESOURCE_DOWNLOAD_LIMIT_EXCEEDED")
    if budget.bytes_used > configuration.max_run_download_bytes:
        raise IngestionError("RUN_DOWNLOAD_LIMIT_EXCEEDED")


def save_download(
    response,
    resource: Resource,
    configuration,
    budget: DownloadBudget,
    progress: ProgressCallback | None = None,
) -> dict:
    directory = configuration.storage_directory / "archives"
    create_private_directory(directory)
    temporary = directory / f"{uuid4().hex}.part"
    digest = hashlib.sha256()
    byte_count = 0
    expected = int(response.headers.get("content-length", "0")) or None
    if response.headers.get("content-encoding"):
        expected = None
    try:
        with temporary.open("xb") as output:
            temporary.chmod(0o600)
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                byte_count += len(chunk)
                budget.bytes_used += len(chunk)
                enforce_download_limit(byte_count, budget, configuration)
                digest.update(chunk)
                output.write(chunk)
                if progress:
                    progress(byte_count, expected)
        sha256 = digest.hexdigest()
        suffix = resource.file_suffix
        if suffix not in {".zip", ".html", ".xml", ".json", ".pdf", ".csv", ".bin"}:
            raise IngestionError("UNSUPPORTED_ARTIFACT_SUFFIX")
        path = directory / f"{sha256}{suffix}"
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    return {
        "source_url": resource.url,
        "path": str(path),
        "sha256": sha256,
        "bytes": byte_count,
        "fetched_at": timestamp,
        "checked_at": timestamp,
        "last_full_check_at": timestamp,
        "etag": response.headers.get("etag"),
        "last_modified": response.headers.get("last-modified"),
    }


def download_resource(
    resource: Resource,
    configuration,
    client: OfficialHttpClient,
    budget: DownloadBudget,
    progress: ProgressCallback | None = None,
) -> DownloadedArtifact:
    manifest_path = configuration.storage_directory / "manifests" / f"{resource.resource_id}.json"
    previous = load_json(manifest_path)
    intact = is_cached_archive_intact(previous, resource)
    if intact and is_recently_checked(previous, configuration):
        if progress:
            progress(previous["bytes"], previous["bytes"])
        return build_downloaded_artifact(resource, previous, "cached")
    headers = build_conditional_headers(previous if intact else None, configuration)
    with client.stream_response(resource.url, headers) as response:
        acquisition_status = "cached" if response.status_code == 304 else "downloaded"
        manifest = select_download_manifest(
            response, resource, configuration, budget, previous, intact, progress
        )
    save_json(manifest_path, manifest)
    return build_downloaded_artifact(resource, manifest, acquisition_status)


def select_download_manifest(
    response, resource, configuration, budget, previous, intact, progress=None
) -> dict:
    if response.status_code == 304:
        if not intact:
            raise IngestionError("INVALID_NOT_MODIFIED_RESPONSE")
        if progress:
            progress(previous["bytes"], previous["bytes"])
        return previous | {"checked_at": datetime.now(UTC).isoformat()}
    expected_bytes = int(response.headers.get("content-length", "0"))
    anticipated = DownloadBudget(budget.bytes_used + expected_bytes)
    enforce_download_limit(expected_bytes, anticipated, configuration)
    return save_download(response, resource, configuration, budget, progress)
