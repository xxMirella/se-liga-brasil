"""Local, bounded, atomic publication primitives."""

import hashlib
import importlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class DatasetManifest:
    schema_version: str
    parser_version: str
    institution_code: str
    year: int
    collection_complete: bool
    input_sha256: str
    parquet_sha256: str
    parquet_file: str
    row_count: int


def connect_analytical_engine(temporary_directory: Path):
    try:
        duckdb = importlib.import_module("duckdb")
    except ModuleNotFoundError as error:
        raise RuntimeError("Install the optional analytical dependency: duckdb>=1.4,<2") from error
    return duckdb.connect(
        config={
            "memory_limit": "256MB",
            "max_temp_directory_size": "512MB",
            "temp_directory": str(temporary_directory),
            "threads": 2,
            "enable_external_access": True,
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
        }
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(partition_directory: Path) -> DatasetManifest | None:
    path = partition_directory / "manifest.json"
    if not path.exists():
        return None
    manifest = DatasetManifest(**json.loads(path.read_text()))
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: DatasetManifest):
    from service.analytical_datasets.contracts import SCHEMA_VERSION, DatasetPartition

    DatasetPartition(manifest.institution_code, manifest.year, manifest.collection_complete)
    if manifest.schema_version not in {SCHEMA_VERSION, "person_voting_timeline.v1"}:
        raise ValueError("Unsupported analytical schema version")
    for digest in (manifest.input_sha256, manifest.parquet_sha256):
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid manifest content hash")
    if manifest.parquet_file != manifest.parquet_sha256 + ".parquet":
        raise ValueError("Invalid manifest file name")
    if type(manifest.row_count) is not int or manifest.row_count < 0:
        raise ValueError("Invalid manifest row count")


def sync_directory(directory: Path):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_manifest(partition_directory: Path, manifest: DatasetManifest):
    with NamedTemporaryFile(mode="w", dir=partition_directory, delete=False) as target:
        temporary_path = Path(target.name)
        json.dump(asdict(manifest), target, sort_keys=True)
        target.flush()
        os.fsync(target.fileno())
    try:
        os.replace(temporary_path, partition_directory / "manifest.json")
        sync_directory(partition_directory)
    finally:
        temporary_path.unlink(missing_ok=True)


def enforce_disk_budget(repository_path: Path, additional_bytes: int, max_bytes: int):
    used_bytes = sum(path.stat().st_size for path in repository_path.rglob("*") if path.is_file())
    if used_bytes + additional_bytes > max_bytes:
        raise ValueError("Analytical repository disk budget exceeded")
