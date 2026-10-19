"""Index official roster names to propose candidates for personal verification."""

from normalization.identity import normalize_person_name


def index_current_members(members) -> dict:
    indexed = {}
    for member in members:
        indexed.setdefault(normalize_person_name(member["nome"]), []).append(member)
    return indexed


def select_member(candidate, members_by_name):
    names = set(candidate["civil_names"] + candidate["public_names"])
    names.update([candidate["civil_name"], candidate["display_name"]])
    matches = {}
    for name in names:
        if name:
            for member in members_by_name.get(normalize_person_name(name), []):
                matches[member["id"]] = member
    return next(iter(matches.values())) if len(matches) == 1 else None
