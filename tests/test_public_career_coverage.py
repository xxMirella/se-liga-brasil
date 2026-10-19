from datetime import date

import pytest

from database.career_coverage import fetch_career_coverage_inputs
from service.public_career_coverage.contracts import CoverageReceipt, CoverageScope
from service.public_career_coverage.planning import (
    build_observed_scopes,
    overlay_political_activity_coverage,
    plan_coverage,
)

TODAY = date(2026, 10, 17)


def scope(person="person-a", **changes):
    values = dict(
        person_id=person,
        institution="TSE",
        domain="elections",
        starts_on=date(2022, 1, 1),
        ends_before=date(2023, 1, 1),
        source="tse",
        partition="2022/SP",
    )
    return CoverageScope(**(values | changes))


def receipt(expected, **changes):
    values = dict(
        scope=expected,
        checked_on=TODAY,
        identity_verified=True,
        enumeration_complete=True,
        source_period_complete=True,
        artifact_verified=True,
        scope_verified=True,
    )
    return CoverageReceipt(**(values | changes))


def test_shared_resource_and_duplicate_scopes():
    first, second = scope(), scope("person-b")
    result = plan_coverage([first, first, second], [], TODAY)
    assert len(result["assessments"]) == 2
    assert len(result["resources"]) == 1
    assert result["resources"][0].person_ids == ("person-a", "person-b")
    assert result["resources"][0].prefer_local


def test_interrupted_enumeration_and_unverified_identity_remain_pending():
    expected = scope()
    result = plan_coverage([expected], [receipt(expected, enumeration_complete=False)], TODAY)
    assert result["assessments"][expected] == "partial"
    assert len(result["resources"]) == 1
    result = plan_coverage([expected], [receipt(expected, identity_verified=False)], TODAY)
    assert result["assessments"][expected] == "identity_unverified"


def test_complete_enumeration_with_no_events_is_complete_for_exact_period():
    expected = scope()
    result = plan_coverage([expected], [receipt(expected)], TODAY)
    assert result["assessments"][expected] == "complete_for_period"
    assert not result["resources"]
    different_period = scope(ends_before=date(2024, 1, 1))
    assert plan_coverage([different_period], [receipt(expected)], TODAY)["resources"]


def test_future_unknown_and_nonapplicable_are_distinct():
    future = scope(starts_on=date(2030, 1, 1), ends_before=date(2031, 1, 1))
    unknown = scope(applicability="unknown")
    nonapplicable = scope(applicability="not_applicable")
    result = plan_coverage([future, unknown, nonapplicable], [], TODAY)
    assert set(result["assessments"].values()) == {"future", "not_assessed", "not_applicable"}
    assert not result["resources"]


def test_discontinuous_exercise_does_not_fabricate_service_between_intervals():
    rows = [
        dict(
            person_id="person-a",
            institution="demo",
            source="demo",
            starts_on=date(2020, 1, 1),
            ends_before=date(2020, 3, 1),
        ),
        dict(
            person_id="person-a",
            institution="demo",
            source="demo",
            starts_on=date(2022, 1, 1),
            ends_before=date(2022, 3, 1),
        ),
    ]
    scopes = build_observed_scopes([], rows, TODAY)
    assert {item.partition for item in scopes} == {"2020", "2022"}
    assert all(item.domain == "offices" for item in scopes)
    assert build_observed_scopes([], [], TODAY) == set()


def test_election_result_does_not_generate_exercise_or_preceding_elections():
    rows = [
        dict(
            person_id="person-a", represented_uf="SP", election_year=2022, election_result="ELEITO"
        )
    ]
    scopes = build_observed_scopes(rows, [], TODAY)
    assert {item.domain for item in scopes} == {"elections"}
    assert {item.partition for item in scopes} == {"2022/SP"}


def test_electoral_coverage_cannot_resolve_legislative_activity_gap():
    report = {"people": [{"person_id": "person-a", "fields": {"full_name": "present"}}]}
    result = overlay_political_activity_coverage(report, {scope(): "complete_for_period"})
    fields = result["people"][0]["fields"]
    assert fields["political_activity"] == "missing_or_unverified"
    assert fields["full_name"] == "present"


def test_future_scopes_do_not_resolve_current_activity_and_summary_matches_fields():
    report = {
        "people": [{"person_id": "person-a", "fields": {"political_activity": "present"}}],
        "missing_by_field": {},
    }
    assessments = {scope(domain=domain): "future" for domain in ("propositions", "votes", "laws")}
    result = overlay_political_activity_coverage(report, assessments)
    assert result["people"][0]["fields"]["political_activity"] == "missing_or_unverified"
    assert result["missing_by_field"] == {"political_activity": 1}


def test_no_people_issues_no_database_query_and_batch_is_bounded():
    class NoQueries:
        def execute(self, *args):
            raise AssertionError("No database access expected")

    assert fetch_career_coverage_inputs(NoQueries(), []) == {
        "candidacies": [],
        "exercises": [],
        "terms": [],
    }
    with pytest.raises(ValueError):
        fetch_career_coverage_inputs(NoQueries(), list(range(1001)))


def test_nationwide_tse_archive_is_shared_between_ufs():
    from service.ingestion.contracts import Resource
    from service.public_career_coverage.assessment import select_shared_tse_resources

    first = scope()
    second = scope("person-b", partition="2022/RJ")
    plan = plan_coverage([first, second], [], TODAY)
    resource = Resource(
        "resource",
        "Candidatos",
        "https://example.test/2022.zip",
        "candidate",
        2022,
        "candidatos-2022",
    )
    selected = select_shared_tse_resources(plan, [resource, resource])
    assert len(selected) == 1
    assert selected[0]["person_ids"] == {"person-a", "person-b"}


def test_open_scope_old_receipt_is_outdated():
    expected = scope(ends_before=date(2027, 1, 1))
    result = plan_coverage([expected], [receipt(expected, checked_on=date(2026, 1, 1))], TODAY)
    assert result["assessments"][expected] == "outdated"
