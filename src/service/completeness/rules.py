"""Domain completeness is independent of crawlers and never fabricates absent facts."""

from collections import Counter
from datetime import date

SATISFIED_STATES = frozenset(
    {"present", "reported_no_assets", "confirmed_no_current_office", "not_applicable"}
)

REQUIRED_FIELDS = (
    "full_name",
    "photo_url",
    "birth_date",
    "education_level",
    "current_political_party",
    "current_salary",
    "declared_assets",
    "declared_wealth",
    "current_public_office",
    "current_office_started_on",
    "political_activity",
    "attendance",
)


def evaluate_person_completeness(row, today=None) -> dict:
    today = today or date.today()
    previous_month = today.replace(day=1).toordinal() - 1
    payroll_threshold = date.fromordinal(previous_month).replace(day=1)
    assets = (
        "present"
        if row["latest_assets"] is not None and row["latest_assets"] == row["latest_election"]
        else "missing"
    )
    if row["reported_no_assets"]:
        assets = (
            "conflicting"
            if row["latest_assets"] == row["latest_election"]
            else "reported_no_assets"
        )
    payroll = (
        "missing"
        if not row["latest_payroll"]
        else "present"
        if row["latest_payroll"] >= payroll_threshold
        else "outdated"
    )
    if row["current_office"] is False:
        payroll = "not_applicable"
    office = (
        "present"
        if row["current_office"] is True
        else "confirmed_no_current_office"
        if row["current_office"] is False
        else "missing_or_unverified"
    )
    fields = {
        "full_name": "present" if row["civil_name"] else "missing",
        "photo_url": "present" if row.get("photo_url") else "missing",
        "birth_date": "present" if row["birth_date"] else "missing",
        "education_level": "present" if row["education_level"] else "missing",
        "current_political_party": "present" if row["current_party"] else "missing_or_unverified",
        "current_salary": payroll,
        "declared_assets": assets,
        "declared_wealth": assets,
        "current_public_office": office,
        "current_office_started_on": (
            "not_applicable" if row["current_office"] is False else
            "present" if row.get("current_office_started_on") else "missing_or_unverified"
        ),
        "political_activity": "partial" if row["has_propositions"] else "missing_or_unverified",
        "attendance": attendance_completeness(row, payroll_threshold),
    }
    return {
        "person_id": row["person_id"],
        "fields": fields,
        "complete": all(fields[name] in SATISFIED_STATES for name in REQUIRED_FIELDS),
        "has_propositions": row["has_propositions"],
        "wealth_scope": "electoral_declaration_not_verified_current_net_worth",
    }


def build_completeness_report(rows, today=None) -> dict:
    people = [evaluate_person_completeness(row, today) for row in rows]
    missing = Counter(
        name
        for person in people
        for name, status in person["fields"].items()
        if status not in SATISFIED_STATES
    )
    return {
        "people": people,
        "total_people": len(people),
        "complete_people": sum(person["complete"] for person in people),
        "missing_by_field": dict(missing),
    }


def attendance_completeness(row, threshold):
    if row["current_office"] is False:
        return "not_applicable"
    period = row.get("latest_attendance_period")
    if period is None:
        return "missing_or_unverified"
    if row.get("attendance_unknown", 0):
        return "partial"
    return "present" if period >= threshold else "outdated"
