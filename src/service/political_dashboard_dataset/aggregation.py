"""Annual observations are evidence, not a reconstruction of unobserved seat occupancy."""

from collections import Counter, defaultdict
from datetime import date

SCHEMA_VERSION = "political_composition_annual.v1"
NATIONAL_INSTITUTIONS = {"senado", "camara", "presidency"}
EXPECTED_SEATS_REFERENCE_YEAR = 2026
EXPECTED_SEATS = {
    ("BR", "senado"): 81,
    ("BR", "camara"): 513,
    ("SP", "alesp"): 94,
    ("RJ", "alerj"): 70,
}


def observation_territories(row):
    observation = row["observation"]
    municipality = observation.get("municipalityIbge")
    uf = observation.get("representedUf")
    if municipality:
        if uf == "DF":
            raise ValueError("DISTRICT_HAS_NO_MUNICIPALITIES")
        return [str(municipality)]
    if row["institution_code"] in NATIONAL_INSTITUTIONS:
        return ["BR", uf] if uf else ["BR"]
    return [uf] if uf else []


def observation_date(row):
    if row.get("date_precision") == "year":
        return None
    value = row["observed_on"]
    return value if isinstance(value, date) else date.fromisoformat(value)


def observation_year(row):
    observed_on = observation_date(row)
    return observed_on.year if observed_on else int(row["year"])


def group_annual_observations(rows, year):
    grouped = defaultdict(list)
    for row in rows:
        if observation_year(row) != year:
            continue
        for territory in observation_territories(row):
            grouped[territory, row["institution_code"]].append(row)
    return grouped


def political_party_identity(observation):
    """Unreconciled abbreviations stay source-qualified; no ambiguous canonical join."""
    code = observation.get("politicalPartyCode")
    abbreviation = observation.get("politicalPartyAbbreviation")
    if not code and not abbreviation:
        return "unreported", "Filiação não informada"
    return str(code or "source:" + abbreviation), abbreviation or str(code)


def latest_person_observations(rows):
    latest = {}
    for row in rows:
        previous = latest.get(row["person_id"])
        if previous is None or (observation_date(row) or date.min) > (
            observation_date(previous) or date.min
        ):
            latest[row["person_id"]] = row
    return latest


def annual_political_parties(rows):
    counts = Counter(political_party_identity(row["observation"]) for row in rows)
    return [
        {"political_party_code": key[0], "abbreviation": key[1], "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_annual_partition(rows, year, territory_code, institution_code):
    latest = latest_person_observations(rows)
    active = [row for row in latest.values() if row["observation"].get("inExercise") is True]
    observed_dates = [
        observed_on for row in latest.values() if (observed_on := observation_date(row)) is not None
    ]
    first_on = min(observed_dates, default=None)
    last_on = max(observed_dates, default=None)
    expected = (
        EXPECTED_SEATS.get((territory_code, institution_code))
        if year == EXPECTED_SEATS_REFERENCE_YEAR
        else None
    )
    simultaneous = (
        first_on is not None and first_on == last_on and len(observed_dates) == len(latest)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "territory_code": territory_code,
        "institution_code": institution_code,
        "office_kinds": sorted(
            {
                row["observation"].get("officeKind")
                for row in rows
                if row["observation"].get("officeKind")
            }
        ),
        "observed_on": str(last_on) if last_on else None,
        "observed_from": str(first_on) if first_on else None,
        "snapshot_on": str(last_on) if simultaneous else None,
        "aggregation_basis": "latest_verified_observation_per_person_within_year"
        if len(observed_dates) == len(latest)
        else "annual_observations_without_exact_snapshot",
        "date_precision": "day" if len(observed_dates) == len(latest) else "year",
        "expected_seats": expected,
        "source_observation_count": len(rows),
        "seat_count": len(active) if simultaneous else None,
        "total": len(active) if simultaneous else None,
        "observed_people_count": len(active),
        "coverage": "observed_partial" if active else "not_available",
        "political_parties": annual_political_parties(active),
        "distinct_people_observed_during_year": count_annual_participants(rows),
        "members": [
            public_member(row) for row in sorted(active, key=lambda item: item["display_name"])
        ],
    }


def count_annual_participants(rows):
    by_political_party = defaultdict(set)
    for row in rows:
        if row["observation"].get("inExercise") is True:
            by_political_party[political_party_identity(row["observation"])].add(row["person_id"])
    return [
        {"political_party_code": key[0], "abbreviation": key[1], "distinct_people": len(people)}
        for key, people in sorted(by_political_party.items())
    ]


def public_member(row):
    observation = row["observation"]
    observed_on = observation_date(row)
    return {
        "person_id": row["person_id"],
        "name": row["display_name"],
        "political_party": political_party_identity(observation)[1],
        "uf": observation.get("representedUf"),
        "capacity": observation.get("capacity"),
        "observed_on": str(observed_on) if observed_on else None,
        "source_record_id": row.get("source_record_id"),
        "person_fact_id": row.get("person_fact_id"),
    }


def build_annual_partitions(rows, year):
    return [
        build_annual_partition(values, year, territory, institution)
        for (territory, institution), values in sorted(
            group_annual_observations(rows, year).items()
        )
    ]
