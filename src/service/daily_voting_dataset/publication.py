"""Consolidate one day from partial normalized batches without touching sources or SQL."""

import fcntl
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from service.analytical_datasets.datasets import MAX_REPOSITORY_BYTES, write_validated_snapshot
from service.analytical_datasets.public_voting_timeline import PUBLIC_TIMELINE_SCHEMA
from service.analytical_datasets.storage import enforce_disk_budget, file_sha256, publish_manifest
from service.daily_voting_dataset.contracts import DailyDatasetManifest, project_daily_vote
from service.daily_voting_dataset.merge import write_merged_parquet
from service.daily_voting_dataset.retirements import (
    append_retirement_checkpoints,
    normalize_retirements,
)
from service.daily_voting_dataset.storage import read_daily_manifest, store_generation


def consolidate_daily_votes(
    input_path,
    repository_path,
    partition,
    parser_version,
    *,
    max_repository_bytes=MAX_REPOSITORY_BYTES,
    retired_voting_ids=(),
    retirement_observed_at=None,
):
    retirements = normalize_retirements(retired_voting_ids, retirement_observed_at)
    if not isinstance(parser_version, str) or not parser_version or len(parser_version) > 100:
        raise ValueError("A bounded parser version is required")
    if type(max_repository_bytes) is not int or max_repository_bytes <= 0:
        raise ValueError("A positive disk budget is required")
    repository_path = Path(repository_path)
    repository_path.mkdir(parents=True, exist_ok=True)
    partition_path = repository_path / partition.relative_path
    partition_path.mkdir(parents=True, exist_ok=True)
    with (repository_path / ".publication.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with TemporaryDirectory(dir=repository_path) as temporary:
            return publish_daily_merge(
                Path(input_path),
                partition_path,
                Path(temporary),
                partition,
                parser_version,
                repository_path,
                max_repository_bytes,
                retirements,
            )


def publish_daily_merge(
    input_path,
    partition_path,
    temporary_path,
    partition,
    parser_version,
    repository_path,
    max_repository_bytes,
    retirements=((), None),
):
    incoming = temporary_path / "incoming.ndjson"
    write_validated_snapshot(input_path, incoming, partition, project_daily_vote)
    append_retirement_checkpoints(incoming, *retirements)
    previous = read_daily_manifest(partition_path, partition)
    previous_state = partition_path / previous.private_state_file if previous else None
    public_path, state_path = temporary_path / "public.parquet", temporary_path / "private.parquet"
    row_count = write_merged_parquet(
        incoming,
        previous_state,
        public_path,
        state_path,
        temporary_path / "spill",
        allow_reprojection=bool(previous and previous.parser_version != parser_version),
    )
    public_hash, state_hash = file_sha256(public_path), file_sha256(state_path)
    if (
        previous
        and previous.private_state_sha256 == state_hash
        and previous.parser_version == parser_version
    ):
        return previous
    public_name, state_name = public_hash + ".parquet", state_hash + ".private.parquet"
    additional = sum(
        path.stat().st_size
        for path, name in ((public_path, public_name), (state_path, state_name))
        if not (partition_path / name).exists()
    )
    enforce_disk_budget(repository_path, additional, max_repository_bytes)
    store_generation(public_path, partition_path, public_name)
    store_generation(state_path, partition_path, state_name)
    manifest = DailyDatasetManifest(
        PUBLIC_TIMELINE_SCHEMA,
        parser_version,
        partition.institution_code,
        partition.occurred_on.year,
        False,
        state_hash,
        public_hash,
        public_name,
        row_count,
        state_hash,
        state_name,
        str(partition.occurred_on),
    )
    archive_daily_generation(partition_path, manifest)
    return manifest


def archive_daily_generation(partition_path, manifest):
    archive_digest = hashlib.sha256(
        json.dumps(asdict(manifest), sort_keys=True).encode()
    ).hexdigest()
    archive_path = partition_path / "history" / archive_digest
    archive_path.mkdir(parents=True, exist_ok=True)
    publish_manifest(archive_path, manifest)
    publish_manifest(partition_path, manifest)
