"""Common keys are evidence, not fuzzy guesses or permanent party-dependent identifiers."""

from normalization.identity import normalize_person_name as fold
from service.identity_resolution.matching import (
    PersonIdentityCandidate,
    PersonIdentityIndex,
    match_source_subject,
    names_match_initials,
    resolve_payroll_recipient,
)


def candidate(identifier="person-one", legal_name="Pessoa Exemplo"):
    return PersonIdentityCandidate(
        identifier, {fold(legal_name)}, {fold("Pessoa Pública")}, {"10/05"}, {"13"}, {123}
    )


def subject(**overrides):
    return {
        "legal_name": "Pessoa Exemplo",
        "parliamentary_names": ["Pessoa Pública"],
        "birthday": "10/05",
        "political_party_code": "55",
        "source_errors": [],
        **overrides,
    }


def test_party_change_does_not_change_resolved_person():
    index = PersonIdentityIndex([candidate()])
    match = match_source_subject(subject(), index)
    assert match["person_id"] == "person-one"
    assert "birth_day_month" in match["matching_fields"]
    assert "political_party_code" not in match["matching_fields"]


def test_homonyms_are_not_automatically_linked():
    index = PersonIdentityIndex([candidate(), candidate("person-two")])
    match = resolve_payroll_recipient(
        {"recipient_name": "Pessoa Exemplo", "recipient_key": "k"}, index, [], []
    )
    assert match["status"] == "ambiguous"


def test_conflicting_birthday_blocks_name_fallback():
    index = PersonIdentityIndex([candidate()])
    evidence = subject(birthday="11/05")
    result = match_source_subject(evidence, index)
    assert result["status"] == "birth_conflict"
    match = resolve_payroll_recipient(
        {"recipient_name": "Pessoa Exemplo", "recipient_key": "k"}, index, [evidence], [result]
    )
    assert match["status"] == "source_conflict"


def test_initials_are_only_expanded_by_an_existing_official_subject():
    assert names_match_initials("Pessoa E", "Pessoa Exemplo")
    assert not names_match_initials("Pessoa Errada", "Pessoa Exemplo")
    index = PersonIdentityIndex([candidate()])
    recipient = {"recipient_name": "Pessoa E", "recipient_key": "k"}
    assert resolve_payroll_recipient(recipient, index, [], [])["status"] == "unmatched"
    evidence = subject()
    match = resolve_payroll_recipient(
        recipient, index, [evidence], [match_source_subject(evidence, index)]
    )
    assert match["person_id"] == "person-one"
    assert match["method"] == "official_subject_bridge"


def test_failed_official_identity_evidence_is_not_treated_as_confirmation():
    index = PersonIdentityIndex([candidate()])
    evidence = subject(source_errors=[{"code": "ALESP_IDENTITY_PROFILE_SUBJECT_MISMATCH"}])
    assert match_source_subject(evidence, index)["status"] == "source_conflict"
    assert match_source_subject(subject(legal_name=None), index)["status"] == "source_unavailable"


def test_reviewed_crosswalk_preserves_birth_conflict_and_requires_target_guards():
    import pytest

    from service.identity_resolution.reviewed import apply_reviewed_crosswalk
    from service.ingestion.contracts import IngestionError

    case = {
        "recipient_name": "Pessoa Exemplo",
        "target_legal_name": "Pessoa Exemplo",
        "target_public_name": "Pessoa Pública",
        "target_birth_date": "1980-05-10",
        "target_political_party_code": "13",
        "source_birthday": "11/05",
    }
    payload = {
        "civilName": "Pessoa Exemplo",
        "displayName": "Pessoa Pública",
        "birthDate": "1980-05-10",
        "politicalPartyCode": "13",
    }
    targets = {
        case["target_legal_name"]: {
            "person_id": "person-one",
            "source_record_id": 1,
            "payload": payload,
        }
    }
    resolutions = [{"recipient_key": "k", "status": "source_conflict"}]
    recipients = [{"recipient_key": "k", "recipient_name": "Pessoa Exemplo"}]
    result = apply_reviewed_crosswalk(resolutions, recipients, [case], targets)
    assert result[0]["person_id"] == "person-one"
    assert result[0]["birth_conflict_preserved"]
    assert payload["birthDate"] == "1980-05-10"
    changed = {
        case["target_legal_name"]: targets[case["target_legal_name"]]
        | {"payload": payload | {"birthDate": "1980-05-12"}}
    }
    with pytest.raises(IngestionError, match="REVIEWED_TARGET_BIRTH_DATE_CHANGED"):
        apply_reviewed_crosswalk(resolutions, recipients, [case], changed)


def test_unique_electoral_name_without_independent_source_identity_requires_review():
    from database.person_identity import build_identity_links

    index = PersonIdentityIndex([candidate()])
    recipient = {
        "recipient_name": "Pessoa Exemplo", "recipient_key": "key", "source_record_ids": [123],
    }
    resolution = resolve_payroll_recipient(recipient, index, [], [])
    assert resolution["status"] == "requires_review"
    assert resolution["suggested_person_id"] == "person-one"
    assert resolution["reason_code"] == "PAYROLL_PERSONAL_IDENTITY_REQUIRED"
    assert "person_id" not in resolution
    assert build_identity_links([resolution], [recipient]) == []


def test_pending_payroll_identity_is_saved_as_review_against_original_source():
    from unittest.mock import Mock

    from database.person_identity import save_payroll_identity_reviews

    connection = Mock()
    connection.execute.return_value.fetchone.return_value = {"total": 1}
    resolutions = [{
        "status": "requires_review", "recipient_key": "key",
        "suggested_person_id": "person-one", "reason_code": "PAYROLL_PERSONAL_IDENTITY_REQUIRED",
    }]
    recipients = [{"recipient_key": "key", "source_record_ids": [123]}]
    assert save_payroll_identity_reviews(connection, 9, resolutions, recipients) == 1
    sql, parameters = connection.execute.call_args.args
    assert "person_identity_review" in sql
    assert "ON CONFLICT DO NOTHING" in sql
    assert parameters[1] == 9
    assert parameters[0].obj == [{
        "source_record_id": 123, "suggested_person_id": "person-one",
        "reason_code": "PAYROLL_PERSONAL_IDENTITY_REQUIRED",
    }]


def test_legacy_name_only_resolution_cannot_recreate_verified_payroll_bridge():
    from database.person_identity import build_identity_links

    legacy = {
        "status": "matched", "recipient_key": "key", "person_id": "person-one",
        "method": "exact_legal_name_and_electoral_scope", "official_subjects": [],
    }
    assert build_identity_links([legacy], []) == []
