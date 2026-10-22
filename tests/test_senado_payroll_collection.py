"""Administrative payroll batches isolate identity failures and stop on source failures."""

from types import SimpleNamespace
from unittest.mock import Mock

from crawlers.senado import payroll_collection
from service.ingestion.contracts import IngestionError


def test_unmatched_person_does_not_discard_other_verified_payments(monkeypatch):
    collect = Mock(side_effect=[IngestionError("SENADO_PAYROLL_NAME_AMBIGUOUS"), {"new": 1}])
    monkeypatch.setattr(payroll_collection, "collect_verified_salary", collect)
    profiles = [{"personId": "first"}, {"personId": "second"}]
    result = payroll_collection.collect_stored_profile_salaries(
        None, SimpleNamespace(payroll_error=None), profiles
    )
    assert result["people"] == [{"person_id": "second", "new": 1}]
    assert result["failures"][0]["code"] == "SENADO_PAYROLL_NAME_AMBIGUOUS"
    assert result["selected_people"] == 2


def test_source_failure_stops_batch_without_more_network_attempts(monkeypatch):
    acquisition = SimpleNamespace(payroll_error=None)

    def unavailable_source(*args):
        acquisition.payroll_error = {"code": "HTTP_ERROR", "status": 503}
        raise IngestionError("HTTP_ERROR", {"status": 503})

    collect = Mock(side_effect=unavailable_source)
    monkeypatch.setattr(payroll_collection, "collect_verified_salary", collect)
    result = payroll_collection.collect_stored_profile_salaries(
        None, acquisition, [{"personId": "first"}, {"personId": "second"}]
    )
    assert len(result["failures"]) == 1 and not result["people"]
    collect.assert_called_once()


def test_salary_dispatch_uses_verified_profiles_without_legislative_request(monkeypatch):
    from crawlers.senado import payroll_routing

    monkeypatch.setattr(
        payroll_routing, "fetch_verified_payroll_profiles",
        lambda *_: [{"personId": "verified"}],
    )
    monkeypatch.setattr(
        payroll_collection, "collect_verified_salary", lambda *_: {"new": 1}
    )
    legislative = Mock(side_effect=AssertionError("Legislative API must not be called"))
    result = payroll_routing.collect_with_verified_salary_profiles(
        SimpleNamespace(connection=None),
        SimpleNamespace(payroll_error=None, configuration=SimpleNamespace(max_people=25)),
        [{"person_id": "verified", "requested_fields": ["current_salary"]}],
        legislative,
    )
    assert result["people"] == [{"person_id": "verified", "new": 1}]
    assert not result["failures"] and result["deferred"] == 0
    legislative.assert_not_called()


def test_legislative_failure_keeps_successful_salary_results(monkeypatch):
    from crawlers.senado import payroll_routing

    monkeypatch.setattr(
        payroll_routing, "fetch_verified_payroll_profiles",
        lambda *_: [{"personId": "verified"}],
    )
    monkeypatch.setattr(
        payroll_collection, "collect_verified_salary", lambda *_: {"new": 1}
    )
    result = payroll_routing.collect_with_verified_salary_profiles(
        SimpleNamespace(connection=None),
        SimpleNamespace(payroll_error=None, configuration=SimpleNamespace(max_people=25)),
        [
            {"person_id": "verified", "requested_fields": ["current_salary"]},
            {"person_id": "unverified", "requested_fields": ["current_salary"]},
        ],
        Mock(side_effect=IngestionError("HTTP_ERROR", {"status": 503})),
    )
    assert result["people"] == [{"person_id": "verified", "new": 1}]
    assert result["failures"][0]["status"] == 503
    assert result["deferred_person_ids"] == ["unverified"]
