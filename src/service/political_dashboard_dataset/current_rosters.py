"""The common roster dates party composition; independent profiles establish canonical identity."""

from service.political_dashboard_dataset.aggregation import build_annual_partitions


def current_camara_roster_partitions(members, artifacts, identities, observed_on):
    if observed_on is None or not members:
        return []
    if len({str(member["id"]) for member in members}) != len(members):
        raise ValueError("CURRENT_ROSTER_DUPLICATE_PROVIDER_IDENTIFIERS")
    evidence = [
        {"url": artifact.resource.url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at}
        for artifact in artifacts
    ]
    rows = [
        current_roster_observation(member, identities[str(member["id"])], observed_on)
        for member in members
        if str(member["id"]) in identities
    ]
    partitions = build_annual_partitions(rows, observed_on.year)
    for partition in partitions:
        partition["aggregation_basis"] = "verified_current_roster_with_personal_identity"
        partition["evidence"] = evidence
        partition["official_roster_size"] = len(members)
        partition["canonical_roster_matches"] = len(rows)
        partition["coverage"] = (
            "verified_current_roster" if len(rows) == len(members) else "observed_partial"
        )
        partition["annual_cohort"] = "current_roster_snapshot_not_full_year_occupancy"
    return partitions


def current_roster_observation(member, identity, observed_on):
    return {
        "person_id": identity["person_id"],
        "display_name": member["nome"],
        "source_record_id": identity["source_record_id"],
        "person_fact_id": identity.get("person_fact_id"),
        "observed_on": observed_on,
        "institution_code": "camara",
        "observation": {
            "institutionCode": "camara",
            "officeKind": "federal_deputy",
            "inExercise": True,
            "politicalPartyAbbreviation": member["siglaPartido"],
            "representedUf": member["siglaUf"],
            "observedOn": observed_on.isoformat(),
            "capacity": None,
            "identityMethod": "independent_official_personal_profile_and_current_roster",
        },
    }
