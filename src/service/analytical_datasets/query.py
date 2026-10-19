"""Bounded local analytical queries; never invoked directly by public HTTP routes."""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from service.analytical_datasets.contracts import DatasetPartition
from service.analytical_datasets.storage import (
    connect_analytical_engine,
    file_sha256,
    read_manifest,
)


def query_person_votes(
    repository_path: Path,
    partition: DatasetPartition,
    person_id: str,
    start_on: date,
    end_on: date,
    *,
    limit: int = 100,
) -> list[dict]:
    canonical_person_id = str(UUID(person_id))
    if start_on > end_on or not 1 <= limit <= 1000:
        raise ValueError("Invalid analytical query bounds")
    partition_path = repository_path / partition.relative_path
    manifest = read_manifest(partition_path)
    if manifest is None:
        return []
    parquet_path = partition_path / manifest.parquet_file
    if parquet_path.parent != partition_path or parquet_path.suffix != ".parquet":
        raise ValueError("Invalid manifest path")
    if (
        manifest.institution_code != partition.institution_code
        or manifest.year != partition.year
        or file_sha256(parquet_path) != manifest.parquet_sha256
    ):
        raise ValueError("Analytical partition integrity mismatch")
    with (
        TemporaryDirectory() as temporary,
        connect_analytical_engine(Path(temporary)) as connection,
    ):
        result = connection.execute(
            """
                SELECT * FROM read_parquet(?, hive_partitioning=false)
                WHERE person_id = ? AND event_start_on <= ? AND event_end_on >= ?
                ORDER BY event_start_on DESC, voting_id LIMIT ?
            """,
            [
                str(parquet_path),
                canonical_person_id,
                end_on.isoformat(),
                start_on.isoformat(),
                limit,
            ],
        )
        columns = [column[0] for column in result.description]
        return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
