"""Bind an explicitly reviewed name pair to one person and one immutable payroll."""

from datetime import date
from uuid import UUID

from normalization.identity import normalize_person_name
from normalization.name_variants import classify_name_variant
from service.ingestion.contracts import IngestionError


def validate_reviewed_name(person, payment, artifact, review, source_code):
    guards = (
        review.get("decision") == "approved_by_user",
        review.get("source_code") == source_code,
        review.get("person_id") == person["person_id"],
        review.get("artifact_sha256") == artifact.sha256,
        review.get("competence") == payment["competence"],
        bool(review.get("review_reference")),
    )
    if not all(guards):
        raise IngestionError("REVIEWED_NAME_SCOPE_MISMATCH")
    try:
        UUID(review["person_id"])
        date.fromisoformat(review["approved_on"])
    except (KeyError, TypeError, ValueError) as error:
        raise IngestionError("REVIEWED_NAME_INVALID_APPROVAL") from error
    registered = normalize_person_name(review["registered_name"])
    if registered != normalize_person_name(person["civil_name"]):
        raise IngestionError("REVIEWED_TARGET_NAME_CHANGED")
    if normalize_person_name(review["published_name"]) != payment["normalizedRecipientName"]:
        raise IngestionError("REVIEWED_PAYROLL_NAME_CHANGED")
    classification = classify_name_variant(person["civil_name"], payment["recipientName"])
    if classification == "requires_other_evidence":
        raise IngestionError("REVIEWED_NAME_VARIANT_NOT_COMPATIBLE")
    return classification


def reviewed_payroll_rows(people, payroll, artifact, reviews, *, source_code, represented_uf):
    indexed_people = {person["person_id"]: person for person in people}
    seen_people, seen_recipients, rows = set(), set(), []
    for review in reviews:
        person = indexed_people.get(review.get("person_id"))
        key = normalize_person_name(review.get("published_name"))
        if person is None or key not in payroll:
            raise IngestionError("REVIEWED_NAME_TARGET_NOT_FOUND")
        if person["person_id"] in seen_people or key in seen_recipients:
            raise IngestionError("REVIEWED_NAME_LINK_AMBIGUOUS")
        payment = payroll[key]
        classification = validate_reviewed_name(person, payment, artifact, review, source_code)
        rows.append(payment | {
            "personId": person["person_id"], "recipientKey": person["person_id"],
            "representedUf": represented_uf, "identityMethod": "human_reviewed_name_variant",
            "identityReview": review | {"classification": classification},
        })
        seen_people.add(person["person_id"])
        seen_recipients.add(key)
    return rows
