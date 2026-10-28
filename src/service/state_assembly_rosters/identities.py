"""Reuse explicit reviewed subject bridges; never link a roster solely by name."""


def verified_subject_identities(resolutions, verified_people):
    identities = {}
    for resolution in resolutions:
        person_id = str(resolution.get("person_id"))
        if resolution["status"] != "matched" or person_id not in verified_people:
            continue
        for subject in resolution.get("official_subjects", []):
            key = subject["source_subject_id"]
            identity = verified_people[person_id]
            if key in identities and identities[key]["person_id"] != person_id:
                raise ValueError("AMBIGUOUS_ASSEMBLY_CANONICAL_IDENTITY_BRIDGE")
            identities[key] = identity
    return identities
