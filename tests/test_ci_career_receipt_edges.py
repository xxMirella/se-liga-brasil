"""Only bounded, matching acquisition receipts certify political career coverage."""

from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from crawlers.receita_federal import pipeline
from database import career_coverage
from service.ingestion.contracts import IngestionError, IngestionSummary
from service.legislative_collection import coverage
from service.orchestration import career_collection
from service.public_career_coverage.contracts import (
    AcquisitionResource,
    CoverageReceipt,
    CoverageScope,
)


def receipt(person="one"):
    scope = CoverageScope(
        person, "senado", "votes", date(2024, 1, 1), date(2024, 2, 1), "senado", "plenary/2024-01"
    )
    return CoverageReceipt(
        scope,
        date(2024, 2, 1),
        True,
        True,
        True,
        True,
        artifact_sha256="a" * 64,
        parser_version="v1",
        scope_verified=True,
    )


def test_career_reads_deduplicate_people_before_three_batched_queries():
    connection = Mock()
    connection.execute.return_value.fetchall.side_effect = [["candidacy"], ["term"], ["exercise"]]
    assert career_coverage.fetch_career_coverage_inputs(connection, ["one", "one"]) == {
        "candidacies": ["candidacy"],
        "terms": ["term"],
        "exercises": ["exercise"],
    }
    assert connection.execute.call_count == 3
    assert all(call.args[1] == (["one"],) for call in connection.execute.call_args_list)


@pytest.mark.parametrize(
    "reader",
    [career_coverage.fetch_career_coverage_inputs, career_coverage.fetch_coverage_receipts],
)
def test_career_read_limits_fail_before_querying(reader):
    connection = Mock()
    with pytest.raises(ValueError, match="1000"):
        reader(connection, [str(index) for index in range(1001)])
    connection.execute.assert_not_called()


def test_missing_receipt_table_and_empty_scope_are_unknown_not_complete():
    connection = Mock()
    assert career_coverage.fetch_coverage_receipts(connection, []) == []
    connection.execute.assert_not_called()
    connection.execute.return_value.fetchone.return_value = {"available": False}
    assert career_coverage.fetch_coverage_receipts(connection, ["one"]) == []


def test_receipt_persistence_requires_parser_and_artifact_and_serializes_dates():
    connection = Mock()
    valid = receipt()
    with pytest.raises(ValueError, match="SHA256"):
        career_coverage.persist_coverage_receipts(
            connection, [replace(valid, artifact_sha256="wrong")]
        )
    with pytest.raises(ValueError, match="parser version"):
        career_coverage.persist_coverage_receipts(connection, [replace(valid, parser_version=" ")])
    assert career_coverage.persist_coverage_receipts(connection, []) == 0
    assert career_coverage.persist_coverage_receipts(connection, [valid]) == 1
    parameters = connection.execute.call_args.args[1][0]
    assert parameters.obj[0]["partition_key"] == "plenary/2024-01"
    assert '"2024-01-01"' in career_coverage._dump_receipts(parameters.obj)
    assert "excluded.checked_on>=stored.checked_on" in connection.execute.call_args.args[0]


def test_receipt_limit_rejects_oversized_generator_without_partial_persistence():
    connection = Mock()
    with pytest.raises(ValueError, match="1000"):
        career_coverage.persist_coverage_receipts(connection, (receipt() for _ in range(1001)))
    connection.execute.assert_not_called()


@pytest.mark.parametrize("has_artifact", [True, False])
def test_senate_collector_attests_only_resolved_people_and_exact_end_exclusive_window(
    monkeypatch, has_artifact
):
    expected = [receipt("one").scope, receipt("two").scope]
    resource = AcquisitionResource(
        "senado",
        "senado",
        "votes",
        "plenary/2024-01",
        ("one", "two"),
        expected_scopes=tuple(expected),
    )
    collect = Mock(
        return_value={
            "artifacts": [{"checked_on": "2024-02-01", "artifact_sha256": "a" * 64}]
            if has_artifact
            else [],
            "resolved_person_ids": ["one"],
        }
    )
    monkeypatch.setattr(coverage, "collect_senate_voting_partitions", collect)
    receipts = coverage.senate_plenary_receipts("db", "storage", resource)
    assert collect.call_args.args[2:] == (date(2024, 1, 1), date(2024, 1, 31))
    assert len(receipts) == (2 if has_artifact else 0)
    if has_artifact:
        assert [item.identity_verified for item in receipts] == [True, False]
    assert set(coverage.career_collectors("db", "storage")) == {("senado", "votes", "plenary")}


def test_dispatch_rejects_duplicate_receipts_and_nonmatching_partition():
    valid = receipt()
    resource = AcquisitionResource("senado", "senado", "votes", "plenary/2024-01", ("one",))
    with pytest.raises(ValueError, match="Duplicate receipt"):
        career_collection.validate_dispatched_receipts(
            resource, [valid, valid], {valid.scope: "partial"}
        )
    with pytest.raises(ValueError, match="outside dispatched scope"):
        career_collection.validate_dispatched_receipts(
            resource, [receipt("two")], {valid.scope: "partial"}
        )


def test_dispatch_preserves_unsupported_and_defers_after_budget_exhaustion(monkeypatch):
    resources = [
        AcquisitionResource("senado", "senado", "votes", "plenary/2024-02", ("one",)),
        AcquisitionResource("senado", "senado", "laws", "2024-02", ("one",)),
        AcquisitionResource("senado", "senado", "votes", "plenary/2024-01", ("one",)),
    ]
    monkeypatch.setattr(
        career_collection,
        "assess_career_coverage",
        Mock(return_value={"resources": resources, "assessments": {}}),
    )
    collector = Mock(return_value=())
    monkeypatch.setattr(career_collection, "persist_coverage_receipts", Mock(return_value=0))
    result = career_collection.dispatch_career_resources(
        "db",
        [{"person_id": "one", "field_name": "political_activity"}],
        date(2024, 3, 1),
        {("senado", "votes"): collector},
        max_resources=1,
    )
    assert result["attempted"] == 1 and result["deferred"] == 1
    assert result["unsupported"] == [("senado", "laws", "2024-02")]


def test_snapshot_guard_rejects_future_observation_and_conflicting_duplicates():
    with pytest.raises(IngestionError, match="CNPJ_ARTIFACT_AFTER_ANALYSIS_DATE"):
        pipeline.source_observed_on(
            SimpleNamespace(fetched_at="2024-02-01T00:00:00Z"), "2024-01-01"
        )
    config = SimpleNamespace(max_matches=1)
    facts = {"key": {"name": "first"}}
    pipeline.add_bounded_fact(facts, "key", {"name": "first"}, config)
    with pytest.raises(IngestionError, match="CNPJ_CONFLICTING_DUPLICATE"):
        pipeline.add_bounded_fact(facts, "key", {"name": "second"}, config)
    with pytest.raises(IngestionError, match="CNPJ_MATCH_LIMIT_EXCEEDED"):
        pipeline.add_bounded_fact(facts, "new", {}, config)


def test_snapshot_ingestion_skips_empty_staging_and_uses_configured_repository(monkeypatch):
    from crawlers.receita_federal import staging

    stage = Mock(
        side_effect=[SimpleNamespace(summary={"valid": 0}), SimpleNamespace(summary={"valid": 1})]
    )
    monkeypatch.setattr(staging, "stage_snapshot_facts", stage)
    repo = Mock()
    repo.ingest_validated_artifact.return_value = IngestionSummary(new=1)
    summaries = pipeline.ingest_snapshot_facts(
        ["one", "two"], "facts", SimpleNamespace(batch_size=500), repo
    )
    assert len(summaries) == 1 and summaries[0].new == 1
    repo.ingest_validated_artifact.assert_called_once()
