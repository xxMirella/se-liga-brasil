"""Batch identity and exports preserve ambiguity, bounds and private evidence."""

import json
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from database import analytical_export as export
from database import person_identity as identity
from service.ingestion.contracts import IngestionError


def connection_with_rows(rows):
    result = SimpleNamespace(fetchall=lambda: rows)
    return SimpleNamespace(execute=Mock(return_value=result))


def test_repeated_candidacies_fold_into_one_person_without_losing_evidence():
    rows = [
        {
            "id": "person",
            "source_record_id": record_id,
            "payload": {
                "civilName": "MARIA DE TESTE",
                "displayName": "Maria Teste",
                "birthDate": "1980-02-29",
                "politicalPartyCode": code,
            },
        }
        for record_id, code in [(1, "A"), (2, "B")]
    ]
    connection = connection_with_rows(rows)
    candidates = identity.fetch_electoral_identity_candidates(connection, "SP", "6", [2022])
    assert len(candidates) == 1
    assert candidates[0].birthdays == {"29/02"}
    assert candidates[0].political_party_codes == {"A", "B"}
    assert candidates[0].source_record_ids == {1, 2}
    assert connection.execute.call_count == 1


def test_identity_without_birth_date_preserves_unknown():
    connection = connection_with_rows(
        [
            {
                "id": "person",
                "source_record_id": 1,
                "payload": {
                    "civilName": "MARIA TESTE",
                    "displayName": "Maria",
                },
            }
        ]
    )
    candidate = identity.fetch_electoral_identity_candidates(connection, "SP", "6", [])[0]
    assert candidate.birthdays == set()
    assert connection.execute.call_args.args[1][-2:] == (None, None)


def test_link_builder_ignores_ambiguous_recipients_and_stabilizes_hash():
    recipient = {"recipient_key": "pay", "recipient_name": "Pessoa teste", "source_record_ids": [1]}
    resolution = {"status": "matched", "recipient_key": "pay", "person_id": "person"}
    first = identity.build_identity_links([resolution | {"fetched_at": "old"}], [recipient])
    second = identity.build_identity_links([resolution | {"fetched_at": "new"}], [recipient])
    assert first[0]["hash"] == second[0]["hash"]
    assert first[0]["evidence"]["payroll_source_record_ids"] == [1]
    assert identity.build_identity_links([resolution | {"status": "ambiguous"}], []) == []


def test_unique_payroll_recipients_are_batched():
    connection = connection_with_rows([{"recipient_key": "key"}])
    assert identity.fetch_payroll_recipients(connection, 9) == [{"recipient_key": "key"}]
    assert connection.execute.call_args.args[1] == (9,)


@pytest.mark.parametrize(
    "rows,ambiguous",
    [
        ([], False),
        ([{"legal_name": "Name", "person_id": "one"}], False),
        (
            [
                {"legal_name": "Name", "person_id": "one"},
                {"legal_name": "Name", "person_id": "one"},
            ],
            False,
        ),
        (
            [
                {"legal_name": "Name", "person_id": "one"},
                {"legal_name": "Name", "person_id": "two"},
            ],
            True,
        ),
    ],
)
def test_reviewed_people_refuse_cross_person_ambiguity(rows, ambiguous):
    connection = connection_with_rows(rows)
    cases = [{"target_legal_name": "Name", "target_birth_date": "1980-01-01"}]
    scope = {"election_year": 2022, "uf": "SP", "office_code": "6"}
    if ambiguous:
        with pytest.raises(IngestionError, match="REVIEWED_PERSONAL_IDENTITY_AMBIGUOUS"):
            identity.fetch_reviewed_people(connection, cases, scope)
    else:
        result = identity.fetch_reviewed_people(connection, cases, scope)
        assert bool(result) == bool(rows)
    assert connection.execute.call_count == 1


def test_payroll_bridge_aborts_before_writes_when_identity_conflicts():
    connection = SimpleNamespace(
        transaction=lambda: nullcontext(),
        execute=Mock(return_value=SimpleNamespace(fetchone=lambda: {"total": 1})),
    )
    with pytest.raises(IngestionError, match="SOURCE_IDENTITY_BRIDGE_CONFLICT"):
        identity.apply_payroll_identity_links(
            connection, 1, [{"person_id": "one"}], "https://example.org"
        )
    queries = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert not any("INSERT INTO" in query for query in queries)


def test_empty_payroll_bridge_never_opens_a_transaction():
    assert identity.apply_payroll_identity_links(None, 1, [], "https://example.org") == {
        "linked_payments": 0,
        "source_identities": 0,
    }


def test_birth_conflicts_are_reviewed_without_overwriting_person():
    connection = SimpleNamespace(execute=Mock())
    identity.save_birth_date_reviews(connection, {"source_id": 1})
    query = connection.execute.call_args.args[0]
    assert "CROSS_SOURCE_BIRTH_DAY_MONTH_DISAGREEMENT" in query
    assert "UPDATE se_liga_brasil.person" not in query


def test_export_snapshot_uses_keyset_not_offset_and_private_file(tmp_path):
    person = "00000000-0000-0000-0000-000000000001"
    row = {"voting_id": 7, "person_id": person, "occurred_on": date(2024, 2, 29)}
    fetch = Mock(side_effect=[[row], []])
    connection = SimpleNamespace(transaction=lambda: nullcontext(), execute=Mock())
    output = tmp_path / "votes.jsonl"
    assert export.export_vote_snapshot(connection, output, "camara", 2024, fetch, maximum=5) == 1
    assert fetch.call_args_list[1].args[-2:] == (7, person)
    assert json.loads(output.read_text())["occurred_on"] == "2024-02-29"
    assert output.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("year,maximum", [(1899, 1), (2201, 1), (2024, 0), (2024, 100001)])
def test_export_rejects_invalid_bounds_before_creating_file(tmp_path, year, maximum):
    output = tmp_path / "votes.jsonl"
    with pytest.raises(ValueError, match="bounds"):
        export.export_vote_snapshot(None, output, "camara", year, Mock(), maximum=maximum)
    assert not output.exists()


def test_export_stops_when_snapshot_limit_exceeded(tmp_path):
    row = {"voting_id": 1, "person_id": "person", "occurred_on": date(2024, 1, 1)}
    fetch = Mock(return_value=[dict(row), dict(row)])
    connection = SimpleNamespace(transaction=lambda: nullcontext(), execute=Mock())
    with pytest.raises(ValueError, match="limit exceeded"):
        export.export_vote_snapshot(connection, tmp_path / "data", "camara", 2024, fetch, maximum=1)
    assert fetch.call_count == 1


@pytest.mark.parametrize("timeline", [False, True])
def test_export_selects_matter_columns_only_for_timeline(timeline):
    connection = connection_with_rows([])
    method = export.fetch_timeline_export_batch if timeline else export.fetch_vote_export_batch
    assert method(connection, "camara", 2024, 0, "person") == []
    query, params = connection.execute.call_args.args
    assert ("AS matter_kind" in query) == timeline
    assert params[1:3] == (date(2024, 1, 1), date(2025, 1, 1))
