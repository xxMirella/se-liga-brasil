"""Public profile composition: observed facts do not imply perpetual current truth."""

from calendar import monthrange
from collections import Counter
from datetime import date
from urllib.parse import urlsplit

from service.public_profile.contracts import PublicProfileError
from service.public_profile.people_contracts import (
    PeopleQuery,
    decode_people_cursor,
    encode_people_cursor,
    validate_as_of,
    validate_person_id,
)
from service.public_profile.term_duration import remaining_term

__all__ = ["PeopleQuery", "get_public_person", "search_people"]


def search_people(repository, query, as_of):
    validate_as_of(as_of)
    cursor = decode_people_cursor(query, as_of)
    with repository.read_snapshot():
        rows = repository.search_people(query, as_of, cursor)
    items = [
        {key: row[key] for key in ("person_id", "display_name", "slug")}
        for row in rows[: query.limit]
    ]
    next_cursor = (
        encode_people_cursor(query, as_of, rows[query.limit - 1])
        if len(rows) > query.limit
        else None
    )
    return {"items": items, "next_cursor": next_cursor, "as_of": as_of.isoformat()}


def public_photo(value):
    try:
        parsed = urlsplit(value or "")
        host = parsed.hostname or ""
        official = host.endswith((".leg.br", ".gov.br", ".jus.br"))
        valid = (
            parsed.scheme == "https" and official and not parsed.username and not parsed.password
        )
        valid = valid and parsed.port in (None, 443) and len(value or "") <= 2048
    except ValueError:
        valid = False
    return {"url": value if valid else None, "status": "available" if valid else "unavailable"}


def public_age(birth_date, as_of):
    if type(birth_date) is not date or birth_date > as_of:
        return {"value": None, "status": "unknown"}
    birthday = (birth_date.month, birth_date.day)
    age = as_of.year - birth_date.year - ((as_of.month, as_of.day) < birthday)
    return {"value": age, "status": "known"}


def completed_tenure(starts_on, as_of):
    months = (as_of.year - starts_on.year) * 12 + as_of.month - starts_on.month
    anniversary_day = min(starts_on.day, monthrange(as_of.year, as_of.month)[1])
    months -= as_of.day < anniversary_day
    return {"years": months // 12, "months": months % 12, "status": "known"}


def public_exercises(rows, as_of):
    overlapping = Counter((row["institution_code"], row["office_kind"]) for row in rows)
    return [
        {
            "exercise_id": row["exercise_id"],
            "term_id": row["term_id"],
            "office_kind": row["office_kind"],
            "represented_uf": row["represented_uf"],
            "institution": {"code": row["institution_code"], "name": row["institution_name"]},
            "starts_on": row["starts_on"].isoformat(),
            "remaining_term": remaining_term(row.get("term_end"), as_of),
            "capacity": row.get("capacity"),
            "tenure": completed_tenure(row["starts_on"], as_of)
            if overlapping[(row["institution_code"], row["office_kind"])] == 1
            else {"years": None, "months": None, "status": "overlapping_exercises"},
        }
        for row in rows[:100]
    ]


def public_political_party(rows):
    empty = {
        "abbreviation": None,
        "name": None,
        "status": "unknown",
        "evidence_kind": None,
        "observed_on": None,
    }
    if not rows:
        return empty
    latest = rows[0]
    same_date = [
        row
        for row in rows
        if row["observed_on"] == latest["observed_on"]
        and (row["evidence_kind"] == "electoral_declaration")
        == (latest["evidence_kind"] == "electoral_declaration")
    ]
    if len({row["abbreviation"] for row in same_date}) > 1:
        return {**empty, "status": "conflicting"}
    status = {
        "official_membership": "membership_reported",
        "administrative": "observed",
        "electoral_declaration": "electoral_declaration",
    }[latest["evidence_kind"]]
    return {
        "abbreviation": latest["abbreviation"],
        "name": latest["name"],
        "status": status,
        "evidence_kind": latest["evidence_kind"],
        "observed_on": latest["observed_on"].isoformat(),
    }


def public_payments(rows, as_of):
    payments = []
    for row in rows[:100]:
        competence = row["competence"]
        age_months = (as_of.year - competence.year) * 12 + as_of.month - competence.month
        freshness = (
            "current_competence"
            if age_months == 0
            else "latest_published"
            if age_months <= 2
            else "outdated"
        )
        payments.append(
            {
                "organization_code": row["organization_code"],
                "office_kind": row["office_kind"],
                "payroll_kind": row["payroll_kind"],
                "competence": competence.strftime("%Y-%m"),
                "currency": row["currency"],
                "gross_amount": str(row["gross_amount"]),
                "deductions_amount": str(row["tax_amount"]),
                "net_amount": str(row["net_amount"]),
                "freshness": freshness,
            }
        )
    return payments


def public_office_status(person, exercises, as_of):
    observed_on = person.get("public_office_status_as_of")
    has_office = person.get("has_current_public_office")
    status = "unknown"
    if exercises:
        has_office, status = True, "documented_exercise"
    elif observed_on and observed_on <= as_of and has_office is not None:
        status = "observed" if observed_on == as_of else "historical_observation"
    else:
        has_office = None
    return {
        "has_current_public_office": has_office,
        "office_kind": person.get("current_public_office_kind") if has_office else None,
        "institution": {
            "code": person.get("snapshot_institution_code"),
            "name": person.get("snapshot_institution_name"),
        }
        if has_office and person.get("snapshot_institution_code")
        else None,
        "status": status,
        "observed_on": observed_on.isoformat() if observed_on and observed_on <= as_of else None,
    }


def get_public_person(repository, person_id, as_of):
    validate_as_of(as_of)
    person_id = validate_person_id(person_id)
    with repository.read_snapshot():
        person = repository.fetch_public_person(person_id)
        if person is None:
            raise PublicProfileError("PERSON_NOT_FOUND", 404)
        exercises = repository.fetch_current_exercises(person_id, as_of)
        affiliations = repository.fetch_public_affiliations(person_id, as_of)
        payments = repository.fetch_latest_public_payments(person_id, as_of)
    return {
        "person_id": person_id,
        "display_name": person["display_name"],
        "slug": person["slug"],
        "as_of": as_of.isoformat(),
        "photo": public_photo(person.get("photo_url")),
        "age": public_age(person.get("birth_date"), as_of),
        "education_level": person.get("education_level"),
        "political_party": public_political_party(affiliations),
        "current_offices": public_exercises(exercises, as_of),
        "public_office": public_office_status(person, exercises, as_of),
        "payments": public_payments(payments, as_of),
        "coverage": {
            "status": "partial",
            "truncated": any(len(rows) > 100 for rows in (exercises, affiliations, payments)),
        },
    }
