"""Shared locking and download orchestration for every source."""

from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from service.acquisition.downloader import download_resource
from service.crawling.ingestion import build_resource_failure
from service.ingestion.contracts import DownloadBudget, IngestionError
from service.observability.download_progress import DownloadProgress
from service.observability.reporting import emit_event
from storage.files import create_private_directory, save_json


@contextmanager
def local_run_lock(storage_directory: Path):
    import fcntl

    create_private_directory(storage_directory)
    lock_path = storage_directory / ".crawler.lock"
    with lock_path.open("a", encoding="utf-8") as lock_file:
        lock_path.chmod(0o600)
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise IngestionError("CRAWLER_ALREADY_RUNNING_LOCALLY") from error
        yield


def download_selected_resources(configuration, client, resources) -> tuple[list, list]:
    downloads = []
    failures = []
    budget = DownloadBudget()
    progress = DownloadProgress(len(resources))
    emit_event("discovery", total_files=len(resources))
    for resource in resources:
        progress.start_file(resource.name)
        try:
            artifact = download_resource(
                resource, configuration, client, budget, progress.update_bytes
            )
            downloads.append(artifact)
            progress.finish_file(succeeded=True, cached=artifact.acquisition_status == "cached")
            emit_event(
                "download",
                resource_id=resource.resource_id,
                kind=resource.kind,
                archive_bytes=artifact.bytes_downloaded,
                acquisition_status=artifact.acquisition_status,
            )
        except Exception as error:
            progress.finish_file(succeeded=False)
            failures.append(build_resource_failure(resource, error, "download"))
    manifest = [asdict(artifact) | {"path": str(artifact.path)} for artifact in downloads]
    save_json(configuration.storage_directory / "download-plan.json", manifest)
    return downloads, failures
