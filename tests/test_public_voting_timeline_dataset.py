"""Public Parquet schema strips private gates and preserves voting grain."""

import json
from uuid import uuid4

import pytest

pytest.importorskip("duckdb")

from service.analytical_datasets import DatasetPartition, publish_person_voting_timeline
from service.analytical_datasets.public_voting_timeline import (
    PUBLIC_TIMELINE_COLUMNS,
    project_public_voting_timeline,
)
from service.analytical_datasets.storage import connect_analytical_engine, read_manifest


def timeline_row(**changes):
    return {
        "person_id": str(uuid4()),
        "voting_id": "42",
        "institution_code": "senado",
        "occurred_on": "2026-10-14",
        "date_precision": "day",
        "vote_choice": "no",
        "participation_status": "voted",
        "evidence_sha256": "a" * 64,
        "validation_status": "verified",
        "matter_kind": "PL",
        "matter_number": "1",
        "matter_year": 2026,
        "matter_name": "Matéria demonstrativa",
        "description": "Texto oficial demonstrativo.",
        "description_origin": "official_text",
        "official_url": "https://www.senado.leg.br/atividade",
        "voting_subject": "Destaque demonstrativo",
        "round_number": 1,
    } | changes


def test_real_public_parquet_roundtrip_preserves_two_turns_and_no_private_gates(tmp_path):
    row = timeline_row()
    source, repository = tmp_path / "input.ndjson", tmp_path / "derived"
    second = row | {"voting_id": "43", "round_number": 2}
    source.write_text("".join(json.dumps(item) + "\n" for item in (row, row, second)))
    original = source.read_bytes()
    partition = DatasetPartition("senado", 2026)
    manifest = publish_person_voting_timeline(source, repository, partition, "test")
    assert manifest.schema_version == "person_voting_timeline.v1" and manifest.row_count == 2
    assert publish_person_voting_timeline(source, repository, partition, "test") == manifest
    partition_path = repository / "legislative/senado/person_voting_timeline/year=2026"
    assert read_manifest(partition_path) == manifest
    with connect_analytical_engine(tmp_path / "spill") as connection:
        relation = connection.read_parquet(
            str(partition_path / manifest.parquet_file), hive_partitioning=False
        )
        assert set(relation.columns) == set(PUBLIC_TIMELINE_COLUMNS)
        assert not {"evidence_sha256", "validation_status", "civil_name", "cpf"} & set(
            relation.columns
        )
        assert relation.count("*").fetchone()[0] == 2
    assert source.read_bytes() == original


def test_official_description_is_explicitly_marked_as_excerpt():
    result = project_public_voting_timeline(
        timeline_row(description="a" * 281), DatasetPartition("senado", 2026)
    )
    assert result["short_description"] == "a" * 280
    assert result["description_kind"] == "official_excerpt"
    assert result["voting_subject"] == "Destaque demonstrativo"


def test_unknown_matter_values_are_null_with_states():
    row = timeline_row(
        matter_kind=None,
        matter_number=None,
        matter_year=None,
        matter_name=None,
        description=None,
        description_origin="unknown",
        official_url=None,
    )
    result = project_public_voting_timeline(row, DatasetPartition("senado", 2026))
    for field in ("matter_kind", "matter_number", "matter_year", "matter_name", "official_url"):
        assert result[field] is None and result[field + "_state"] == "missing"
    assert result["short_description"] is None and result["description_kind"] == "unknown"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/matter",
        "javascript:alert(1)",
        "http://www.senado.leg.br/",
        "https://user:password@www.senado.leg.br/",
        "https://www.senado.leg.br/#private",
    ],
)
def test_nonofficial_or_private_urls_are_rejected(url):
    with pytest.raises(ValueError):
        project_public_voting_timeline(
            timeline_row(official_url=url), DatasetPartition("senado", 2026)
        )


def test_unverified_fact_is_not_promoted_and_conflicts_do_not_replace_partition(tmp_path):
    source, repository = tmp_path / "input.ndjson", tmp_path / "derived"
    row = timeline_row()
    source.write_text(json.dumps(row) + "\n")
    partition = DatasetPartition("senado", 2026)
    first = publish_person_voting_timeline(source, repository, partition, "test")
    source.write_text(json.dumps(row | {"validation_status": "pending"}) + "\n")
    with pytest.raises(ValueError, match="verified"):
        publish_person_voting_timeline(source, repository, partition, "test")
    source.write_text(json.dumps(row) + "\n" + json.dumps(row | {"vote_choice": "yes"}) + "\n")
    with pytest.raises(ValueError, match="Conflicting"):
        publish_person_voting_timeline(source, repository, partition, "test")
    assert (
        read_manifest(repository / "legislative/senado/person_voting_timeline/year=2026") == first
    )


def test_public_and_existing_dataset_coexist_without_replacing_each_other(tmp_path):
    from service.analytical_datasets import publish_person_votes
    from service.analytical_datasets.contracts import VOTE_COLUMNS

    row = timeline_row()
    repository = tmp_path / "derived"
    private_input, public_input = tmp_path / "private.ndjson", tmp_path / "public.ndjson"
    private_input.write_text(json.dumps({field: row[field] for field in VOTE_COLUMNS}) + "\n")
    public_input.write_text(json.dumps(row) + "\n")
    partition = DatasetPartition("senado", 2026)
    old_manifest = publish_person_votes(private_input, repository, partition, "test")
    new_manifest = publish_person_voting_timeline(public_input, repository, partition, "test")
    assert read_manifest(repository / partition.relative_path) == old_manifest
    assert new_manifest.schema_version != old_manifest.schema_version
    assert len(list(repository.rglob("manifest.json"))) == 2
