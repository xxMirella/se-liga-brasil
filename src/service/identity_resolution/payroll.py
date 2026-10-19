"""Reconcile source payroll recipients with existing people using reusable evidence rules."""

from database.person_identity import (
    apply_payroll_identity_links,
    build_identity_links,
    fetch_electoral_identity_candidates,
    fetch_payroll_recipients,
    fetch_reviewed_people,
)
from service.identity_resolution.matching import (
    PersonIdentityIndex,
    match_source_subject,
    resolve_payroll_recipient,
)
from service.identity_resolution.reviewed import apply_reviewed_crosswalk


def resolve_payroll_identities(
    connection, source_id, source_url, subjects, *, uf, office_code, reviewed_cases=()
):
    candidates = PersonIdentityIndex(
        fetch_electoral_identity_candidates(connection, uf, office_code, years=None)
    )
    subject_matches = [match_source_subject(subject, candidates) for subject in subjects]
    recipients = fetch_payroll_recipients(connection, source_id)
    resolutions = [
        resolve_payroll_recipient(recipient, candidates, subjects, subject_matches)
        for recipient in recipients
    ]
    if reviewed_cases:
        targets = fetch_reviewed_people(connection, reviewed_cases, reviewed_cases[0]["scope"])
        resolutions = apply_reviewed_crosswalk(resolutions, recipients, reviewed_cases, targets)
    result = apply_payroll_identity_links(
        connection, source_id, build_identity_links(resolutions, recipients), source_url
    )
    unresolved = [item for item in resolutions if item["status"] != "matched"]
    return result | {
        "recipients": len(recipients),
        "unresolved_recipients": len(unresolved),
        "unresolved": unresolved,
        "resolutions": resolutions,
    }
