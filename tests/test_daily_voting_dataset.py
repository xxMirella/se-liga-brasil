"""Daily partial merges with real Parquet and immutable revision checkpoints."""

import json
from datetime import date
from uuid import uuid4

import pytest

pytest.importorskip("duckdb")

from service.analytical_datasets.storage import connect_analytical_engine
from service.daily_voting_dataset import DailyVotingPartition, consolidate_daily_votes
from service.daily_voting_dataset.storage import read_daily_manifest


def row(**changes):
    return {
        "person_id": str(uuid4()),
        "voting_id": "senado:plenary:7106",
        "institution_code": "senado",
        "occurred_on": "2026-10-14",
        "date_precision": "day",
        "vote_choice": "yes",
        "participation_status": "voted",
        "evidence_sha256": "a" * 64,
        "validation_status": "verified",
        "matter_kind": "PL",
        "matter_number": "1",
        "matter_year": 2026,
        "matter_name": "Matéria demonstrativa",
        "description": None,
        "description_origin": "unknown",
        "official_url": None,
        "voting_subject": "Texto principal",
        "round_number": 1,
        "source_observed_at": "2026-10-15T12:00:00+00:00",
    } | changes


def publish(tmp_path, rows):
    source = tmp_path / "partial.ndjson"
    source.write_text("".join(json.dumps(item) + "\n" for item in rows))
    return consolidate_daily_votes(source, tmp_path / "derived", partition(), "test")


def partition():
    return DailyVotingPartition("senado", date(2026, 10, 14))


def read_public(tmp_path, manifest):
    path = tmp_path / "derived" / partition().relative_path / manifest.parquet_file
    with connect_analytical_engine(tmp_path / "spill") as connection:
        result = connection.execute(
            "SELECT * FROM read_parquet(?,hive_partitioning=false)", [str(path)]
        )
        fields = [field[0] for field in result.description]
        return [dict(zip(fields, values, strict=True)) for values in result.fetchall()]


def test_partial_files_preserve_people_and_distinct_turns(tmp_path):
    first = row()
    second = row()
    publish(tmp_path, [first])
    latest = publish(
        tmp_path, [second, first | {"voting_id": "senado:plenary:7107", "round_number": 2}]
    )
    assert latest.row_count == 3
    public = read_public(tmp_path, latest)
    assert {item["person_id"] for item in public} == {first["person_id"], second["person_id"]}
    assert (
        not {"source_observed_at", "evidence_sha256", "record_sha256", "validation_status"}
        & public[0].keys()
    )


def test_replay_and_old_observation_do_not_replace_new_correction(tmp_path):
    first = row()
    original = publish(tmp_path, [first])
    assert publish(tmp_path, [first]) == original
    correction = first | {"vote_choice": "no", "source_observed_at": "2026-10-16T12:00:00Z"}
    corrected = publish(tmp_path, [correction])
    assert read_public(tmp_path, corrected)[0]["vote_choice"] == "no"
    assert publish(tmp_path, [first]) == corrected
    path = tmp_path / "derived" / partition().relative_path
    assert (path / original.private_state_file).exists()
    assert len(list((path / "history").rglob("manifest.json"))) == 2


def test_equal_observation_conflict_preserves_current_manifest(tmp_path):
    first = row()
    manifest = publish(tmp_path, [first])
    with pytest.raises(ValueError, match="Conflicting"):
        publish(tmp_path, [first | {"vote_choice": "no"}])
    assert (
        read_daily_manifest(tmp_path / "derived" / partition().relative_path, partition())
        == manifest
    )


def test_interrupted_manifest_switch_keeps_previous_public_and_private(tmp_path, monkeypatch):
    import service.daily_voting_dataset.publication as publication

    first = row()
    manifest = publish(tmp_path, [first])

    def interrupt(*arguments):
        raise OSError("Simulated interruption")

    monkeypatch.setattr(publication, "publish_manifest", interrupt)
    with pytest.raises(OSError, match="interruption"):
        publish(tmp_path, [row()])
    assert (
        read_daily_manifest(tmp_path / "derived" / partition().relative_path, partition())
        == manifest
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"source_observed_at": "2026-10-15T12:00:00"},
        {"occurred_on": "2026-10-15"},
        {"occurred_on": "2026-10", "date_precision": "month"},
        {"validation_status": "pending"},
    ],
)
def test_untrusted_or_wrong_daily_input_never_publishes(tmp_path, changes):
    with pytest.raises(ValueError):
        publish(tmp_path, [row(**changes)])
    assert not list((tmp_path / "derived").rglob("manifest.json"))


def test_equivalent_timezone_observations_are_same_revision(tmp_path):
    first = row()
    manifest = publish(tmp_path, [first])
    assert (
        publish(tmp_path, [first | {"source_observed_at": "2026-10-15T09:00:00-03:00"}]) == manifest
    )


def test_empty_partial_does_not_delete_consolidated_votes(tmp_path):
    manifest = publish(tmp_path, [row()])
    assert publish(tmp_path, []) == manifest
    assert len(read_public(tmp_path, manifest)) == 1


def test_merge_order_does_not_change_latest_public_content(tmp_path):
    first = row()
    correction = first | {"vote_choice": "no", "source_observed_at": "2026-10-16T12:00:00Z"}
    forward, backward = tmp_path / "forward", tmp_path / "backward"
    forward.mkdir()
    backward.mkdir()
    publish(forward, [first])
    forward_latest = publish(forward, [correction])
    publish(backward, [correction])
    backward_latest = publish(backward, [first])
    assert forward_latest.parquet_sha256 == backward_latest.parquet_sha256
    assert forward_latest.private_state_sha256 == backward_latest.private_state_sha256


def test_explicit_retirement_hides_all_people_and_blocks_old_replay(tmp_path):
    first, second = row(), row()
    original = publish(tmp_path, [first, second])
    source = tmp_path / "partial.ndjson"
    source.write_text("")
    retired = consolidate_daily_votes(
        source,
        tmp_path / "derived",
        partition(),
        "test",
        retired_voting_ids=[first["voting_id"]],
        retirement_observed_at="2026-10-16T12:00:00Z",
    )
    assert retired.row_count == 0 and read_public(tmp_path, retired) == []
    assert publish(tmp_path, [first, second]) == retired
    assert (tmp_path / "derived" / partition().relative_path / original.private_state_file).exists()
    other_voting = row(voting_id="senado:plenary:7107", round_number=2)
    latest = publish(tmp_path, [other_voting])
    assert latest.row_count == 1
    assert read_public(tmp_path, latest)[0]["voting_id"] == "senado:plenary:7107"


def test_only_newer_verified_nominal_observation_can_restore_retired_vote(tmp_path):
    first = row()
    publish(tmp_path, [first])
    source = tmp_path / "partial.ndjson"
    source.write_text("")
    consolidate_daily_votes(
        source,
        tmp_path / "derived",
        partition(),
        "test",
        retired_voting_ids=[first["voting_id"]],
        retirement_observed_at="2026-10-16T12:00:00+00:00",
    )
    newer = first | {"source_observed_at": "2026-10-17T12:00:00Z", "vote_choice": "no"}
    manifest = publish(tmp_path, [newer])
    assert manifest.row_count == 1 and read_public(tmp_path, manifest)[0]["vote_choice"] == "no"


def test_retirement_requires_explicit_timestamp_and_bounded_event_keys(tmp_path):
    source = tmp_path / "partial.ndjson"
    source.write_text("")
    with pytest.raises(ValueError, match="timestamp"):
        consolidate_daily_votes(
            source,
            tmp_path / "derived",
            partition(),
            "test",
            retired_voting_ids=["senado:plenary:7106"],
        )
    with pytest.raises(ValueError, match="1000"):
        consolidate_daily_votes(
            source,
            tmp_path / "derived",
            partition(),
            "test",
            retired_voting_ids=("senado:plenary:7106" for _ in range(1001)),
            retirement_observed_at="2026-10-16T12:00:00Z",
        )


def test_new_parser_reprojects_same_evidence_without_changing_observation(tmp_path):
    original = row()
    publish(tmp_path, [original])
    source = tmp_path / "reprojection.ndjson"
    source.write_text(json.dumps(original | {"matter_name": "Título normalizado"}) + "\n")
    manifest = consolidate_daily_votes(source, tmp_path / "derived", partition(), "test-v2")
    assert read_public(tmp_path, manifest)[0]["matter_name"] == "Título normalizado"
    replay = consolidate_daily_votes(source, tmp_path / "derived", partition(), "test-v2")
    assert replay == manifest


def test_new_parser_does_not_hide_conflicting_source_evidence(tmp_path):
    original = row()
    publish(tmp_path, [original])
    source = tmp_path / "conflict.ndjson"
    source.write_text(
        json.dumps(
            original
            | {
                "matter_name": "Outro título",
                "evidence_sha256": "b" * 64,
            }
        )
        + "\n"
    )
    with pytest.raises(ValueError, match="Conflicting"):
        consolidate_daily_votes(source, tmp_path / "derived", partition(), "test-v2")
