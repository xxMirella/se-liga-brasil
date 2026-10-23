"""Deterministic source identity matching with explicit scope and ambiguity handling."""

from dataclasses import dataclass, field

from normalization.identity import normalize_person_name

NAME_CONNECTORS = frozenset({"da", "das", "de", "do", "dos"})


@dataclass
class PersonIdentityCandidate:
    person_id: str
    legal_names: set[str] = field(default_factory=set)
    public_names: set[str] = field(default_factory=set)
    birthdays: set[str] = field(default_factory=set)
    political_party_codes: set[str] = field(default_factory=set)
    source_record_ids: set[int] = field(default_factory=set)


class PersonIdentityIndex:
    def __init__(self, candidates: list[PersonIdentityCandidate]) -> None:
        self.people = {candidate.person_id: candidate for candidate in candidates}
        self.legal_names = self.index_names(candidates, "legal_names")
        self.public_names = self.index_names(candidates, "public_names")

    @staticmethod
    def index_names(candidates, field_name):
        indexed = {}
        for candidate in candidates:
            for name in getattr(candidate, field_name):
                indexed.setdefault(name, set()).add(candidate.person_id)
        return indexed


def names_match_initials(published_name: str, complete_name: str) -> bool:
    published = [
        x for x in normalize_person_name(published_name).split() if x not in NAME_CONNECTORS
    ]
    complete = [x for x in normalize_person_name(complete_name).split() if x not in NAME_CONNECTORS]
    if len(published) != len(complete):
        return False
    return all(
        short == full or (len(short) == 1 and full.startswith(short))
        for short, full in zip(published, complete, strict=True)
    )


def match_source_subject(subject: dict, candidates: PersonIdentityIndex) -> dict:
    if not subject.get("legal_name"):
        return {"status": "source_unavailable"}
    name = normalize_person_name(subject["legal_name"])
    public_names = {
        normalize_person_name(value) for value in subject.get("parliamentary_names", [])
    }
    birthday = subject.get("birthday")
    if subject.get("source_errors"):
        return {"status": "source_conflict"}
    people = set(candidates.legal_names.get(name, set()))
    for public_name in public_names:
        people.update(candidates.public_names.get(public_name, set()))
    matches, conflicts = [], []
    for person_id in people:
        candidate = candidates.people[person_id]
        legal = name in candidate.legal_names
        public = bool(public_names & candidate.public_names)
        if not legal and not (public and birthday and birthday in candidate.birthdays):
            continue
        if birthday and candidate.birthdays and birthday not in candidate.birthdays:
            conflicts.append(candidate.person_id)
            continue
        matches.append(candidate)
    if len(matches) != 1:
        return {
            "status": "ambiguous"
            if len(matches) > 1
            else "birth_conflict"
            if conflicts
            else "unmatched"
        }
    candidate = matches[0]
    return {
        "matching_fields": matching_fields(subject, candidate),
        "status": "matched",
        "person_id": candidate.person_id,
        "method": "official_legal_or_public_name_birth_and_electoral_scope",
        "candidate_source_record_ids": sorted(candidate.source_record_ids),
    }


def resolve_payroll_recipient(recipient: dict, candidates, subjects, subject_matches) -> dict:
    published = recipient["recipient_name"]
    name = normalize_person_name(published)
    exact = candidates.legal_names.get(name, set())
    member_matches = set()
    evidence = []
    source_conflict = False
    for subject, match in zip(subjects, subject_matches, strict=True):
        if not subject.get("legal_name"):
            continue
        if match["status"] in {"birth_conflict", "source_conflict", "ambiguous"}:
            source_conflict |= names_match_initials(published, subject["legal_name"])
        if match["status"] != "matched":
            continue
        if names_match_initials(published, subject["legal_name"]):
            member_matches.add(match["person_id"])
            evidence.append(subject | {"matching": match})
    if source_conflict:
        return {"status": "source_conflict", "recipient_key": recipient["recipient_key"]}
    people = (
        (set(exact) & member_matches) if exact and member_matches else (set(exact) | member_matches)
    )
    if exact and member_matches and not people:
        return {"status": "source_conflict", "recipient_key": recipient["recipient_key"]}
    if len(people) != 1:
        return {
            "status": "ambiguous" if people else "unmatched",
            "recipient_key": recipient["recipient_key"],
        }
    person_id = next(iter(people))
    candidate = candidates.people[person_id]
    return payroll_identity_decision(recipient, candidate, evidence)


def payroll_identity_decision(recipient, candidate, evidence):
    person_id = candidate.person_id
    if not evidence:
        return {
            "status": "requires_review",
            "recipient_key": recipient["recipient_key"],
            "suggested_person_id": person_id,
            "reason_code": "PAYROLL_PERSONAL_IDENTITY_REQUIRED",
            "candidate_source_record_ids": sorted(candidate.source_record_ids),
        }
    return {
        "status": "matched",
        "recipient_key": recipient["recipient_key"],
        "person_id": person_id,
        "method": "official_subject_bridge",
        "candidate_source_record_ids": sorted(candidate.source_record_ids),
        "official_subjects": evidence,
    }


def matching_fields(subject, candidate):
    name = normalize_person_name(subject["legal_name"])
    public_names = {
        normalize_person_name(value) for value in subject.get("parliamentary_names", [])
    }
    birthday = subject.get("birthday")
    fields = ["legal_name"] if name in candidate.legal_names else []
    if public_names & candidate.public_names:
        fields.append("public_name")
    if birthday and birthday in candidate.birthdays:
        fields.append("birth_day_month")
    if subject.get("political_party_code") in candidate.political_party_codes:
        fields.append("political_party_code")
    return fields
