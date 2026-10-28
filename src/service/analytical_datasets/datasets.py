"""Publish a validated complete snapshot of one shared institution/year partition."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from service.analytical_datasets.contracts import (
    SCHEMA_VERSION,
    DatasetPartition,
    validate_person_vote,
)
from service.analytical_datasets.storage import (
    DatasetManifest,
    connect_analytical_engine,
    enforce_disk_budget,
    file_sha256,
    publish_manifest,
    read_manifest,
    sync_directory,
)

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 16 * 1024
MAX_REPOSITORY_BYTES = 256 * 1024 * 1024


def write_validated_snapshot(
    input_path: Path,
    output_path: Path,
    partition: DatasetPartition,
    validate_record=validate_person_vote,
):
    digest = hashlib.sha256()
    consumed_bytes = 0
    with input_path.open("rb") as source, output_path.open("wb") as target:
        while line := source.readline(MAX_LINE_BYTES + 1):
            consumed_bytes += len(line)
            if len(line) > MAX_LINE_BYTES or consumed_bytes > MAX_INPUT_BYTES:
                raise ValueError("Analytical input limit exceeded")
            record = validate_record(json.loads(line), partition)
            encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
            digest.update(encoded)
            target.write(encoded)
    return digest.hexdigest()


def write_person_votes_parquet(
    snapshot_path: Path,
    parquet_path: Path,
    temporary_path: Path,
    column_types=None,
):
    with connect_analytical_engine(temporary_path) as connection:
        columns = {
            column: "VARCHAR"
            for column in (
                "person_id",
                "voting_id",
                "institution_code",
                "occurred_on",
                "date_precision",
                "vote_choice",
                "participation_status",
                "evidence_sha256",
                "validation_status",
                "event_start_on",
                "event_end_on",
            )
        }
        columns = column_types or columns
        connection.read_json(
            str(snapshot_path), columns=columns, format="newline_delimited"
        ).create("votes")
        conflicts = connection.execute("""
            SELECT 1 FROM (SELECT DISTINCT * FROM votes)
            GROUP BY person_id, voting_id HAVING count(*) > 1 LIMIT 1
        """).fetchone()
        if conflicts:
            raise ValueError("Conflicting versions of the same person/voting fact")
        connection.sql("SELECT DISTINCT * FROM votes ORDER BY person_id,voting_id").write_parquet(
            str(parquet_path), compression="zstd"
        )
        return connection.execute("SELECT count(*) FROM (SELECT DISTINCT * FROM votes)").fetchone()[
            0
        ]


def publish_person_votes(
    input_path: Path,
    repository_path: Path,
    partition: DatasetPartition,
    parser_version: str,
    *,
    max_repository_bytes: int = MAX_REPOSITORY_BYTES,
) -> DatasetManifest:
    return publish_validated_dataset(
        input_path,
        repository_path,
        partition,
        parser_version,
        max_repository_bytes=max_repository_bytes,
    )


def publish_validated_dataset(
    input_path,
    repository_path,
    partition,
    parser_version,
    *,
    max_repository_bytes=MAX_REPOSITORY_BYTES,
    schema_version=SCHEMA_VERSION,
    validate_record=validate_person_vote,
    column_types=None,
):
    if schema_version not in {
        SCHEMA_VERSION, "person_voting_timeline.v1", "person_voting_timeline.v2",
    }:
        raise ValueError("Unsupported dataset schema")
    if not isinstance(parser_version, str) or not parser_version or len(parser_version) > 100:
        raise ValueError("A bounded parser version is required")
    if type(max_repository_bytes) is not int or max_repository_bytes <= 0:
        raise ValueError("A positive repository disk budget is required")
    repository_path.mkdir(parents=True, exist_ok=True)
    dataset_name = schema_version.split(".")[0]
    partition_path = repository_path / (
        f"legislative/{partition.institution_code}/{dataset_name}/year={partition.year}"
    )
    partition_path.mkdir(parents=True, exist_ok=True)
    with (repository_path / ".publication.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with TemporaryDirectory(dir=repository_path) as temporary:
            return publish_partition_snapshot(
                input_path,
                partition_path,
                Path(temporary),
                partition,
                parser_version,
                repository_path,
                max_repository_bytes,
                schema_version,
                validate_record,
                column_types,
            )


def publish_partition_snapshot(
    input_path,
    partition_path,
    temporary_path,
    partition,
    parser_version,
    repository_path,
    max_repository_bytes,
    schema_version=SCHEMA_VERSION,
    validate_record=validate_person_vote,
    column_types=None,
):
    snapshot_path = temporary_path / "validated.ndjson"
    input_hash = write_validated_snapshot(input_path, snapshot_path, partition, validate_record)
    previous = read_manifest(partition_path)
    if is_reusable_snapshot(
        previous,
        input_hash,
        parser_version,
        partition,
        partition_path,
        schema_version,
    ):
        return previous
    parquet_path = temporary_path / "votes.parquet"
    row_count = write_person_votes_parquet(
        snapshot_path,
        parquet_path,
        temporary_path / "spill",
        column_types,
    )
    parquet_hash = file_sha256(parquet_path)
    filename = parquet_hash + ".parquet"
    destination = partition_path / filename
    additional = 0 if destination.exists() else parquet_path.stat().st_size
    enforce_disk_budget(repository_path, additional, max_repository_bytes)
    with parquet_path.open("rb") as parquet_file:
        os.fsync(parquet_file.fileno())
    os.replace(parquet_path, destination)
    sync_directory(partition_path)
    manifest = DatasetManifest(
        schema_version,
        parser_version,
        partition.institution_code,
        partition.year,
        partition.collection_complete,
        input_hash,
        parquet_hash,
        filename,
        row_count,
    )
    publish_manifest(partition_path, manifest)
    return manifest


def is_reusable_snapshot(
    previous,
    input_hash,
    parser_version,
    partition,
    partition_path,
    schema_version=SCHEMA_VERSION,
):
    if previous is None:
        return False
    matches = (
        previous.input_sha256 == input_hash
        and previous.parser_version == parser_version
        and previous.schema_version == schema_version
        and previous.collection_complete == partition.collection_complete
    )
    path = partition_path / previous.parquet_file
    return matches and path.is_file() and file_sha256(path) == previous.parquet_sha256
