"""A complete official roster can be counted without inventing canonical person matches."""

from datetime import datetime
from zoneinfo import ZoneInfo

from service.political_dashboard_dataset.aggregation import build_annual_partitions

EXPECTED_SEATS = {
    "AC": 24,
    "AL": 27,
    "AM": 24,
    "AP": 24,
    "BA": 63,
    "CE": 46,
    "DF": 24,
    "ES": 30,
    "GO": 41,
    "MA": 42,
    "MG": 77,
    "MS": 24,
    "MT": 24,
    "PA": 41,
    "PB": 36,
    "PE": 49,
    "PI": 30,
    "PR": 54,
    "RJ": 70,
    "RN": 24,
    "RO": 24,
    "RR": 24,
    "RS": 55,
    "SC": 40,
    "SE": 24,
    "SP": 94,
    "TO": 24,
}

LABEL_ALIASES = {
    "UNIÃO BRASIL": "UNIÃO",
    "UNIAO": "UNIÃO",
    "PC DO B": "PCdoB",
    "PCDOB": "PCdoB",
    "REP": "REPUBLICANOS",
    "SDD": "SOLIDARIEDADE",
    "PODEMOS": "PODE",
}


def aggregate_current_roster(members, institution, uf, evidence, identities=None):
    identities = identities or {}
    identifiers = [row["provider_subject_id"] for row in members]
    if not members or len(set(identifiers)) != len(identifiers):
        raise ValueError("ASSEMBLY_ROSTER_EMPTY_OR_DUPLICATE_IDENTIFIERS")
    if len(members) > EXPECTED_SEATS[uf]:
        raise ValueError("ASSEMBLY_ROSTER_EXCEEDS_SIMULTANEOUS_SEAT_CAPACITY")
    observed_on = (
        datetime.fromisoformat(evidence["fetched_at"]).astimezone(ZoneInfo("America/Belem")).date()
    )
    rows = [
        roster_observation(
            member, identities.get(member["provider_subject_id"]), institution, uf, observed_on
        )
        for member in members
    ]
    partition = build_annual_partitions(rows, observed_on.year)[0]
    partition.update(
        aggregation_basis="verified_current_official_assembly_roster",
        coverage="verified_current_roster",
        evidence=[evidence],
        official_roster_size=len(members),
        canonical_roster_matches=sum(key in identities for key in identifiers),
        annual_cohort="current_roster_snapshot_not_full_year_occupancy",
    )
    partition["expected_seats"] = EXPECTED_SEATS[uf]
    if len(members) < EXPECTED_SEATS[uf]:
        partition["coverage"] = "observed_partial"
        partition["coverage_limitation"] = (
            "publisher_lists_fewer_current_members_than_expected_seats"
        )
    if uf in {"AC", "AM", "PB", "PI", "RN"}:
        partition.update(
            aggregation_basis="official_active_legislature_registry_not_individual_exercise_confirmation",
            coverage="observed_active_registry",
            coverage_limitation="active_registry_not_individually_confirmed_exercise",
        )
    if uf == "AP":
        partition.update(
            aggregation_basis="official_directory_during_reported_migration",
            coverage="observed_partial",
            snapshot_on=None,
            coverage_limitation="official_portal_migration_updates_may_be_delayed",
        )
    if uf == "RS":
        partition.update(
            aggregation_basis="official_roster_reconciled_with_dated_exercise_evidence",
            coverage="observed_partial",
            snapshot_on=None,
            coverage_limitation="monthly_attendance_and_profiles_not_simultaneous_seat_snapshot",
        )
    return partition


def roster_observation(member, identity, institution, uf, observed_on):
    name = member.get("name", "").strip()
    if not name:
        raise ValueError("ASSEMBLY_ROSTER_MEMBER_NAME_REQUIRED")
    political_party = (member.get("political_party") or "").strip().upper()
    political_party = LABEL_ALIASES.get(political_party, political_party)
    return {
        "person_id": identity["person_id"]
        if identity
        else f"{institution}:deputy:{member['provider_subject_id']}",
        "display_name": name,
        "source_record_id": identity.get("source_record_id") if identity else None,
        "observed_on": observed_on,
        "institution_code": institution,
        "observation": {
            "institutionCode": institution,
            "officeKind": "district_deputy" if uf == "DF" else "state_deputy",
            "representedUf": uf,
            "inExercise": True,
            "politicalPartyAbbreviation": political_party or None,
            "politicalPartyCode": f"source:{institution}:{political_party}"
            if political_party
            else None,
            "observedOn": observed_on.isoformat(),
        },
    }


def preserve_official_assembly_rosters(partitions, published):
    replacements = {
        (row["payload"]["territory_code"], row["payload"]["institution_code"]): row["payload"]
        for row in published
    }
    return [
        row
        for row in partitions
        if (row["territory_code"], row["institution_code"]) not in replacements
    ] + list(replacements.values())


def preserve_dated_ma_diary(candidate, published):
    """Do not let an incomplete directory overwrite a reviewed dated official roster."""
    if candidate["territory_code"] != "MA" or candidate.get("total", 0) >= 42:
        return candidate
    for row in published:
        previous = row["payload"]
        if (
            previous["territory_code"] == "MA"
            and previous.get("official_roster_publication_on")
            and previous.get("total") == 42
        ):
            return previous
    return candidate
