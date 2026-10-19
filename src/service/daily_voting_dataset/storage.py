"""Private dual-file checkpoint; one atomic manifest activates public and private generations."""

import json
import os
import re
from dataclasses import fields

from service.analytical_datasets.storage import (
    DatasetManifest,
    file_sha256,
    sync_directory,
    validate_manifest,
)
from service.daily_voting_dataset.contracts import DailyDatasetManifest


def read_daily_manifest(partition_path, partition):
    path = partition_path / "manifest.json"
    if not path.exists():
        return None
    manifest = DailyDatasetManifest(**json.loads(path.read_text()))
    base_fields = {field.name for field in fields(DatasetManifest)}
    validate_manifest(DatasetManifest(**{key: getattr(manifest, key) for key in base_fields}))
    if manifest.occurred_on != str(partition.occurred_on):
        raise ValueError("Daily checkpoint voting day mismatch")
    if (
        manifest.institution_code != partition.institution_code
        or manifest.year != partition.occurred_on.year
    ):
        raise ValueError("Daily checkpoint partition mismatch")
    if not re.fullmatch(r"[a-f0-9]{64}", manifest.private_state_sha256):
        raise ValueError("Invalid private checkpoint hash")
    if manifest.private_state_file != manifest.private_state_sha256 + ".private.parquet":
        raise ValueError("Invalid private checkpoint path")
    for filename, expected in (
        (manifest.parquet_file, manifest.parquet_sha256),
        (manifest.private_state_file, manifest.private_state_sha256),
    ):
        if file_sha256(partition_path / filename) != expected:
            raise ValueError("Daily checkpoint integrity mismatch")
    return manifest


def store_generation(source_path, partition_path, filename):
    with source_path.open("rb") as artifact:
        os.fsync(artifact.fileno())
    os.replace(source_path, partition_path / filename)
    sync_directory(partition_path)
