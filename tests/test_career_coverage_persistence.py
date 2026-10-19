from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

from database.career_coverage import fetch_coverage_receipts, persist_coverage_receipts
from database.operations import read_sql_file, strip_transaction_wrapper
from service.orchestration.career_collection import validate_dispatched_receipts
from service.public_career_coverage.contracts import (
    AcquisitionResource,
    CoverageReceipt,
    CoverageScope,
)
from service.public_career_coverage.planning import plan_coverage


def make_receipt(person_id):
    scope = CoverageScope(
        person_id, "DEMO", "votes", date(2022, 1, 1), date(2023, 1, 1), "demo", "2022"
    )
    return CoverageReceipt(
        scope,
        date(2026, 10, 17),
        True,
        True,
        True,
        True,
        artifact_sha256="a" * 64,
        parser_version="v1",
        scope_verified=True,
    )


def test_receipt_requires_artifact_and_parser_before_database_access():
    receipt = make_receipt(str(uuid4()))
    with pytest.raises(ValueError, match="SHA256"):
        persist_coverage_receipts(None, [replace(receipt, artifact_sha256=None)])
    with pytest.raises(ValueError, match="parser"):
        persist_coverage_receipts(None, [replace(receipt, parser_version="")])


def test_receipt_cannot_escape_dispatched_person_or_interval():
    receipt = make_receipt(str(uuid4()))
    resource = AcquisitionResource("demo", "DEMO", "votes", "2022", (receipt.scope.person_id,))
    validate_dispatched_receipts(resource, [receipt], {receipt.scope: "partial"})
    other = replace(receipt, scope=replace(receipt.scope, ends_before=date(2024, 1, 1)))
    with pytest.raises(ValueError, match="outside"):
        validate_dispatched_receipts(resource, [other], {receipt.scope: "partial"})
    with pytest.raises(ValueError, match="Duplicate"):
        validate_dispatched_receipts(resource, [receipt, receipt], {receipt.scope: "partial"})


@pytest.mark.integration
def test_persistence_is_idempotent_and_incomplete_enumeration_remains_pending(integration_database):
    connection = integration_database
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0018_career_coverage_receipts.sql"))
    )
    person_id = str(uuid4())
    connection.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('fixture','Fixture','https://example.invalid','api')"
    )
    connection.execute(
        "INSERT INTO se_liga_brasil.source_record"
        "(source_id,external_key,source_url,content_sha256,payload) "
        "SELECT id,'fixture','https://example.invalid',repeat('a',64),'{}' "
        "FROM se_liga_brasil.source WHERE code='fixture'"
    )
    connection.execute(
        "INSERT INTO se_liga_brasil.person"
        "(id,slug,civil_name,display_name,primary_record_id) "
        "SELECT %s,%s,'Pessoa Teste','Teste',id "
        "FROM se_liga_brasil.source_record WHERE external_key='fixture'",
        (person_id, str(person_id)),
    )
    receipt = make_receipt(person_id)
    assert persist_coverage_receipts(connection, [receipt]) == 1
    persist_coverage_receipts(connection, [receipt])
    rows = fetch_coverage_receipts(connection, [person_id])
    assert len(rows) == 1
    assert plan_coverage([receipt.scope], rows, receipt.checked_on)["resources"] == []
    persist_coverage_receipts(connection, [replace(receipt, enumeration_complete=False)])
    rows = fetch_coverage_receipts(connection, [person_id])
    assert plan_coverage([receipt.scope], rows, receipt.checked_on)["resources"]
    persist_coverage_receipts(connection, [replace(receipt, scope_verified=False)])
    rows = fetch_coverage_receipts(connection, [person_id])
    assert plan_coverage([receipt.scope], rows, receipt.checked_on)["resources"]


def test_dispatch_budget_is_checked_before_database_access():
    from service.orchestration.career_collection import dispatch_career_resources

    with pytest.raises(ValueError, match="budget"):
        dispatch_career_resources(None, [], date.today(), {}, max_resources=0)


def test_dispatch_bounds_lazy_callback_consumption(monkeypatch):
    import service.orchestration.career_collection as dispatch

    receipt = make_receipt(str(uuid4()))
    resource = AcquisitionResource("demo", "DEMO", "votes", "2022", (receipt.scope.person_id,))
    monkeypatch.setattr(
        dispatch,
        "assess_career_coverage",
        lambda *args: {"resources": [resource], "assessments": {receipt.scope: "partial"}},
    )
    consumed = []

    def unlimited(resource):
        while True:
            consumed.append(1)
            yield receipt

    tasks = [{"person_id": receipt.scope.person_id, "field_name": "political_activity"}]
    with pytest.raises(ValueError, match="1000"):
        dispatch.dispatch_career_resources(
            None, tasks, date.today(), {("demo", "votes"): unlimited}
        )
    assert len(consumed) == 1001


def test_dispatch_resource_budget_and_shared_people(monkeypatch):
    import service.orchestration.career_collection as dispatch

    first = make_receipt(str(uuid4()))
    second = replace(first, scope=replace(first.scope, person_id=str(uuid4())))
    resource = AcquisitionResource(
        "demo", "DEMO", "votes", "2022", (first.scope.person_id, second.scope.person_id)
    )
    newer = replace(resource, partition="2023")
    monkeypatch.setattr(
        dispatch,
        "assess_career_coverage",
        lambda *args: {"resources": [resource, newer], "assessments": {}},
    )
    calls = []

    def collector(request):
        calls.append(request)
        return ()

    tasks = [
        {"person_id": person, "field_name": "political_activity"} for person in resource.person_ids
    ]
    result = dispatch.dispatch_career_resources(
        None, tasks, date.today(), {("demo", "votes"): collector}, max_resources=1
    )
    assert len(calls) == 1
    assert calls[0] == newer
    assert calls[0].person_ids == resource.person_ids
    assert result["attempted"] == 1
    assert result["deferred"] == 1
