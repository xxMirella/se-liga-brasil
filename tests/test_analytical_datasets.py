"""Real local Parquet round trips; fixtures never touch the production database."""

import json
from datetime import date
from uuid import uuid4

import pytest

pytest.importorskip("duckdb")

from service.analytical_datasets import DatasetPartition, publish_person_votes, query_person_votes


def vote(**changes):
    return {
        "person_id": str(uuid4()),
        "voting_id": "42",
        "institution_code": "senado",
        "occurred_on": "2026-10-14",
        "date_precision": "day",
        "vote_choice": "yes",
        "participation_status": "voted",
        "evidence_sha256": "a" * 64,
        "validation_status": "verified",
    } | changes


def write_votes(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_real_parquet_roundtrip_and_replay(tmp_path):
    row = vote()
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    write_votes(source, [row, row])
    partition = DatasetPartition("senado", 2026)
    manifest = publish_person_votes(source, repository, partition, "test-v1")
    assert manifest.row_count == 1
    assert publish_person_votes(source, repository, partition, "test-v1") == manifest
    rows = query_person_votes(
        repository, partition, row["person_id"], date(2026, 1, 1), date(2026, 12, 31)
    )
    assert len(rows) == 1 and rows[0]["vote_choice"] == "yes"


@pytest.mark.parametrize(
    "changes",
    [
        {"cpf": "unexpected"},
        {"validation_status": "unverified"},
        {"participation_status": "absent"},
        {"voting_id": str(uuid4())},
        {"occurred_on": "2025-10-14"},
    ],
)
def test_invalid_inputs_never_publish_a_manifest(tmp_path, changes):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    write_votes(source, [vote(**changes)])
    with pytest.raises(ValueError):
        publish_person_votes(source, repository, DatasetPartition("senado", 2026), "test")
    assert not list(repository.rglob("manifest.json"))


def test_conflicting_facts_do_not_replace_current_partition(tmp_path):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    partition, row = DatasetPartition("senado", 2026), vote()
    write_votes(source, [row])
    first = publish_person_votes(source, repository, partition, "test")
    write_votes(source, [row, row | {"vote_choice": "no"}])
    with pytest.raises(ValueError, match="Conflicting"):
        publish_person_votes(source, repository, partition, "test")
    current = json.loads((repository / partition.relative_path / "manifest.json").read_text())
    assert current["parquet_sha256"] == first.parquet_sha256


def test_corrupt_parquet_is_detected_before_query(tmp_path):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    partition, row = DatasetPartition("senado", 2026), vote()
    write_votes(source, [row])
    manifest = publish_person_votes(source, repository, partition, "test")
    (repository / partition.relative_path / manifest.parquet_file).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="integrity"):
        query_person_votes(
            repository, partition, row["person_id"], date(2026, 1, 1), date(2026, 12, 31)
        )


def test_complete_empty_partition_is_not_a_missing_manifest(tmp_path):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    source.write_text("")
    manifest = publish_person_votes(source, repository, DatasetPartition("senado", 2026), "test")
    assert manifest.row_count == 0


def test_corrected_snapshot_replaces_pointer_and_preserves_original(tmp_path):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    partition, row = DatasetPartition("senado", 2026), vote()
    write_votes(source, [row])
    first = publish_person_votes(source, repository, partition, "v1")
    write_votes(source, [row | {"vote_choice": "no"}])
    original_bytes = source.read_bytes()
    second = publish_person_votes(source, repository, partition, "v2")
    assert source.read_bytes() == original_bytes
    assert first.parquet_sha256 != second.parquet_sha256
    assert (repository / partition.relative_path / first.parquet_file).is_file()
    rows = query_person_votes(
        repository, partition, row["person_id"], date(2026, 1, 1), date(2026, 12, 31)
    )
    assert rows[0]["vote_choice"] == "no" and len(rows) == 1
    third = publish_person_votes(source, repository, partition, "v3")
    assert third.parser_version == "v3" and third.parquet_sha256 == second.parquet_sha256


@pytest.mark.parametrize("precision,occurred_on", [("month", "2026-10"), ("year", "2026")])
def test_partial_dates_preserve_precision_and_overlap_filter(tmp_path, precision, occurred_on):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    row = vote(date_precision=precision, occurred_on=occurred_on)
    write_votes(source, [row])
    partition = DatasetPartition("senado", 2026)
    publish_person_votes(source, repository, partition, "test")
    rows = query_person_votes(
        repository, partition, row["person_id"], date(2026, 10, 15), date(2026, 10, 15)
    )
    assert rows[0]["occurred_on"] == occurred_on
    assert rows[0]["date_precision"] == precision


def test_publication_failure_preserves_previous_manifest(tmp_path, monkeypatch):
    from service.analytical_datasets import datasets

    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    partition, row = DatasetPartition("senado", 2026), vote()
    write_votes(source, [row])
    first = publish_person_votes(source, repository, partition, "test")
    write_votes(source, [row | {"vote_choice": "no"}])

    def refuse_manifest(*arguments):
        raise OSError("Simulated publication interruption")

    monkeypatch.setattr(datasets, "publish_manifest", refuse_manifest)
    with pytest.raises(OSError, match="interruption"):
        publish_person_votes(source, repository, partition, "test")
    current = json.loads((repository / partition.relative_path / "manifest.json").read_text())
    assert current["parquet_sha256"] == first.parquet_sha256


@pytest.mark.parametrize(
    "field,value", [("person_id", None), ("vote_choice", []), ("date_precision", {})]
)
def test_malformed_scalar_fields_have_explicit_validation_error(tmp_path, field, value):
    source = tmp_path / "votes.ndjson"
    write_votes(source, [vote(**{field: value})])
    with pytest.raises(ValueError):
        publish_person_votes(source, tmp_path / "derived", DatasetPartition("senado", 2026), "v1")


def test_repository_budget_failure_does_not_publish(tmp_path):
    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    write_votes(source, [vote()])
    with pytest.raises(ValueError, match="budget"):
        publish_person_votes(
            source, repository, DatasetPartition("senado", 2026), "v1", max_repository_bytes=1
        )
    assert not list(repository.rglob("manifest.json"))


def test_manifest_traversal_is_rejected_before_file_access(tmp_path):
    from service.analytical_datasets.storage import read_manifest

    source, repository = tmp_path / "votes.ndjson", tmp_path / "derived"
    partition = DatasetPartition("senado", 2026)
    write_votes(source, [vote()])
    publish_person_votes(source, repository, partition, "v1")
    manifest_path = repository / partition.relative_path / "manifest.json"
    data = json.loads(manifest_path.read_text())
    data["parquet_file"] = "../../outside.parquet"
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="file name"):
        read_manifest(manifest_path.parent)
