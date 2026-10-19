"""Apply reviewed identifier crosswalks only when source and target guards still hold."""

from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError


def validate_target_identity(payload, case) -> None:
    fields = (("civilName", "target_legal_name"), ("displayName", "target_public_name"))
    if any(
        normalize_person_name(payload[key]) != normalize_person_name(case[expected])
        for key, expected in fields
    ):
        raise IngestionError("REVIEWED_TARGET_NAME_CHANGED")
    if payload.get("birthDate") != case["target_birth_date"]:
        raise IngestionError("REVIEWED_TARGET_BIRTH_DATE_CHANGED")
    if payload.get("politicalPartyCode") != case["target_political_party_code"]:
        raise IngestionError("REVIEWED_TARGET_PARTY_CHANGED")


def apply_reviewed_crosswalk(resolutions, recipients, cases, targets) -> list:
    result = {row["recipient_key"]: row for row in resolutions}
    by_name = {}
    for recipient in recipients:
        by_name.setdefault(normalize_person_name(recipient["recipient_name"]), []).append(recipient)
    for case in cases:
        matches = by_name.get(normalize_person_name(case["recipient_name"]), [])
        if len(matches) != 1:
            raise IngestionError("REVIEWED_PAYROLL_RECIPIENT_AMBIGUOUS")
        target = targets.get(case["target_legal_name"])
        if target is None:
            raise IngestionError("REVIEWED_PERSONAL_IDENTITY_MISSING")
        validate_target_identity(target["payload"], case)
        key = matches[0]["recipient_key"]
        current = result[key]
        person_id = str(target["person_id"])
        if current["status"] == "matched" and current["person_id"] != person_id:
            raise IngestionError("REVIEWED_IDENTITY_BRIDGE_CONFLICT")
        result[key] = {
            "status": "matched",
            "recipient_key": key,
            "person_id": person_id,
            "method": "reviewed_personal_identity_evidence",
            "official_subjects": [],
            "candidate_source_record_ids": [target["source_record_id"]],
            "reviewed_crosswalk": case,
            "birth_conflict_preserved": bool(case.get("source_birthday"))
            and case["source_birthday"]
            != case["target_birth_date"][8:10] + "/" + case["target_birth_date"][5:7],
        }
    return list(result.values())
