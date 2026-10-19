"""Bounded partition planning shared across people, with average O(1) indexed lookups."""

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, timedelta

from normalization.periods import month_intervals
from service.completeness.rules import REQUIRED_FIELDS, SATISFIED_STATES
from service.public_career_coverage.contracts import AcquisitionResource, CoverageScope

SATISFIED_COVERAGE = frozenset({"complete_for_period", "not_applicable", "future"})
LEGISLATIVE_INSTITUTIONS = frozenset({"camara", "senado", "alesp", "alerj", "cmsp"})


def assess_scope(scope, receipts, today, freshness_days=30):
    """Receipts must attest the exact interval; a summary row cannot prove enumeration."""
    if scope.starts_on > today:
        return "future"
    if scope.applicability != "applicable":
        return "not_applicable" if scope.applicability == "not_applicable" else "not_assessed"
    usable = [receipt for receipt in receipts if receipt.checked_on <= today]
    if not usable:
        return "not_assessed"
    receipt = max(usable, key=lambda item: item.checked_on)
    if not receipt.identity_verified:
        return "identity_unverified"
    if receipt.status == "unavailable":
        return "unavailable"
    complete = (
        receipt.enumeration_complete
        and receipt.source_period_complete
        and receipt.artifact_verified
        and receipt.scope_verified
    )
    if not complete:
        return "partial"
    if scope.ends_before > today and receipt.checked_on < today - timedelta(days=freshness_days):
        return "outdated"
    covered_until = min(scope.ends_before - timedelta(days=1), today)
    if receipt.checked_on < covered_until:
        return "partial"
    return "complete_for_period"


def plan_coverage(scopes, receipts, today, freshness_days=30):
    """Deduplicate exact intervals and group downloads without issuing any network call."""
    receipt_index = defaultdict(list)
    for receipt in receipts:
        receipt_index[receipt.scope].append(receipt)
    assessments = {}
    resources = defaultdict(set)
    resource_scopes = defaultdict(list)
    for scope in dict.fromkeys(scopes):
        status = assess_scope(scope, receipt_index[scope], today, freshness_days)
        assessments[scope] = status
        if status not in SATISFIED_COVERAGE and scope.applicability == "applicable":
            key = (scope.source, scope.institution, scope.domain, scope.partition)
            resources[key].add(scope.person_id)
            resource_scopes[key].append(scope)
    return {
        "assessments": assessments,
        "resources": [
            AcquisitionResource(
                *key, tuple(sorted(people)), expected_scopes=tuple(resource_scopes[key])
            )
            for key, people in resources.items()
        ],
    }


def build_observed_scopes(candidacies, exercises, today):
    """Expect observed elections and actual exercise only; earlier career remains unknown."""
    scopes = set()
    for row in candidacies:
        year, uf = row["election_year"], row["represented_uf"]
        if year <= today.year:
            scopes.add(
                CoverageScope(
                    row["person_id"],
                    "TSE",
                    "elections",
                    date(year, 1, 1),
                    date(year + 1, 1, 1),
                    "tse",
                    f"{year}/{uf}",
                )
            )
    for row in exercises:
        scopes.update(build_exercise_scopes(row, today))
    return scopes


def build_exercise_scopes(row, today):
    start = row["starts_on"]
    if start is None:
        return
    end = min(row["ends_before"] or today + timedelta(days=1), today + timedelta(days=1))
    for year in range(start.year, end.year + 1):
        lower, upper = max(start, date(year, 1, 1)), min(end, date(year + 1, 1, 1))
        if lower < upper:
            yield CoverageScope(
                row["person_id"],
                row["institution"],
                "offices",
                lower,
                upper,
                row["source"],
                str(year),
            )


def overlay_political_activity_coverage(
    report, assessments, required_domains=("propositions", "votes", "laws")
):
    """Preserve the existing queue contract; do not resolve other fields accidentally."""
    person_states = defaultdict(list)
    person_domains = defaultdict(set)
    for scope, status in assessments.items():
        if scope.domain in required_domains and status != "future":
            person_states[scope.person_id].append(status)
            person_domains[scope.person_id].add(scope.domain)
    people = []
    for person in report["people"]:
        statuses = person_states.get(person["person_id"], [])
        has_domains = set(required_domains) <= person_domains[person["person_id"]]
        complete = (
            has_domains and statuses and all(status in SATISFIED_COVERAGE for status in statuses)
        )
        state = (
            "present"
            if complete
            else (
                "partial" if person.get("has_propositions") or statuses else "missing_or_unverified"
            )
        )
        fields = person["fields"] | {"political_activity": state}
        people.append(
            person
            | {
                "fields": fields,
                "complete": all(fields.get(name) in SATISFIED_STATES for name in REQUIRED_FIELDS),
            }
        )
    missing = Counter(
        field
        for person in people
        for field, status in person["fields"].items()
        if status not in SATISFIED_STATES
    )
    return report | {
        "people": people,
        "missing_by_field": dict(missing),
        "complete_people": sum(person["complete"] for person in people),
    }


def build_activity_scopes(
    scopes, domains=("propositions", "votes", "laws"), institutions=LEGISLATIVE_INSTITUTIONS
):
    """Each verified exercise interval requires independent legislative-domain coverage."""
    return {
        activity
        for scope in scopes
        if scope.domain == "offices" and scope.institution in institutions
        for activity in monthly_activity_scopes(scope, domains)
    }


def monthly_activity_scopes(scope, domains):
    for start, end in month_intervals(scope.starts_on, scope.ends_before):
        for domain in domains:
            channels = (
                ("plenary/", "committee/")
                if domain == "votes" and scope.source == "senado"
                else ("",)
            )
            for channel in channels:
                yield replace(
                    scope,
                    domain=domain,
                    starts_on=start,
                    ends_before=end,
                    partition=channel + start.strftime("%Y-%m"),
                )
