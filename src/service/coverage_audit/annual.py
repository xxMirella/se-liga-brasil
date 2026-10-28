"""Describe evidence coverage without assuming historical existence or continuous occupancy."""

import re
from collections import Counter, defaultdict

from service.political_dashboard.contracts import STATE_NAMES

STATE_LEGISLATURES = dict(
    zip(
        (
            "AC",
            "AL",
            "AM",
            "AP",
            "BA",
            "CE",
            "DF",
            "ES",
            "GO",
            "MA",
            "MG",
            "MS",
            "MT",
            "PA",
            "PB",
            "PE",
            "PI",
            "PR",
            "RJ",
            "RN",
            "RO",
            "RR",
            "RS",
            "SC",
            "SE",
            "SP",
            "TO",
        ),
        (
            "aleac",
            "aleal",
            "aleam",
            "alap",
            "alba",
            "alece",
            "cldf",
            "ales",
            "alego",
            "alema",
            "almg",
            "alems",
            "almt",
            "alepa",
            "alpb",
            "alepe",
            "alepi",
            "alep",
            "alerj",
            "alrn",
            "alero",
            "alrr",
            "alrs",
            "alesc",
            "alese",
            "alesp",
            "aleto",
        ),
        strict=True,
    )
)

CANONICAL_ID = re.compile(r"^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
UNKNOWN_LABELS = {"", "filiação não informada", "partido não informado", "unknown"}
COMPLETE_COVERAGES = {"observed_complete", "verified_current_roster"}


def partition_metrics(payload, canonical_ids):
    people = payload.get("members", []) + payload.get("segments", [])
    labels = [str(row.get("political_party") or "").casefold() for row in people]
    political_parties = payload.get("political_parties", [])
    identifiers = {row.get("person_id") for row in people if row.get("person_id")}
    result = {
        key: payload.get(key)
        for key in (
            "year",
            "territory_code",
            "institution_code",
            "total",
            "coverage",
            "snapshot_on",
            "aggregation_basis",
            "institutional_status",
            "expected_seats",
        )
    }
    result.update(
        {
            "named_records": len(people),
            "distinct_source_or_canonical_ids": len(identifiers),
            "canonical_profile_links": len(identifiers & canonical_ids),
            "dangling_uuid_identifiers": sorted(
                identifier
                for identifier in identifiers
                if CANONICAL_ID.fullmatch(identifier) and identifier not in canonical_ids
            ),
            "records_without_political_party": sum(label in UNKNOWN_LABELS for label in labels),
            "records_without_source": sum(
                not (row.get("official_url") or row.get("evidence")) for row in people
            ),
            "political_parties_sum": sum(row.get("count", 0) for row in political_parties),
            "historical_roster_records": len(payload.get("historical_roster", [])),
            "election_observations": len(payload.get("election_observations", [])),
            "source_urls": sorted(
                {row["url"] for row in payload.get("evidence", []) if row.get("url")}
            ),
        }
    )
    result["status"] = evidence_status(result)
    return result


def evidence_status(row):
    if row.get("institutional_status") in {
        "suspended",
        "suspended_whole_year",
        "closed",
        "not_applicable",
    }:
        return "institutionally_not_applicable"
    if row.get("coverage") == "legislature_roster_only":
        return "legislature_roster_not_annual_caucus"
    if not row.get("total") and not row.get("named_records"):
        return "published_without_usable_composition"
    if row.get("coverage") == "observed_active_registry":
        return "active_registry_not_effective_exercise_confirmation"
    if row.get("aggregation_basis") in {
        "verified_year_end_status_of_current_roster_cohort",
        "verified_year_end_status_of_historical_legislature_rosters",
    }:
        return "partial_historical_legislature_cohort"
    if row.get("coverage") in COMPLETE_COVERAGES:
        return "complete_at_documented_snapshot"
    if row.get("named_records") and row.get("records_without_political_party"):
        return "named_evidence_with_party_gaps"
    if row.get("aggregation_basis") == "dated_official_government_observations":
        return "dated_event_not_continuous_occupancy"
    return "partial_documented_evidence"


def year_ranges(years):
    ranges = []
    for year in sorted(set(years)):
        if ranges and year == ranges[-1][1] + 1:
            ranges[-1][1] = year
        else:
            ranges.append([year, year])
    return ranges


def scope_inventory(catalog):
    scopes = [("BR", name) for name in ("presidency", "senado", "camara")]
    for uf in STATE_NAMES:
        scopes.extend([(uf, STATE_LEGISLATURES[uf]), (uf, "senado"), (uf, "camara")])
        scopes.append((uf, "district_government" if uf == "DF" else "state_government"))
    for municipality in catalog["municipalities"]:
        scopes.extend(
            (municipality["ibge_code"], institution)
            for institution in (
                "municipal_government",
                "municipal_council",
            )
        )
    return scopes


def annual_scope_coverage(rows, catalog, start, end):
    indexed = defaultdict(list)
    for row in rows:
        if start <= row["year"] <= end:
            indexed[row["territory_code"], row["institution_code"]].append(row)
    results = []
    for territory, institution in scope_inventory(catalog):
        observed = indexed.pop((territory, institution), [])
        statuses = defaultdict(list)
        for row in observed:
            statuses[row["status"]].append(row["year"])
        published = {row["year"] for row in observed}
        results.append(
            {
                "territory_code": territory,
                "institution_code": institution,
                "published_years": len(published),
                "status_year_ranges": {
                    key: year_ranges(years) for key, years in sorted(statuses.items())
                },
                "absent_year_ranges": year_ranges(set(range(start, end + 1)) - published),
            }
        )
    return results, [row for rows in indexed.values() for row in rows]


def summarize_scopes(scopes):
    grouped = defaultdict(Counter)
    for scope in scopes:
        key = scope["institution_code"]
        grouped[key]["catalog_territories"] += 1
        grouped[key]["territories_with_any_published_year"] += bool(scope["published_years"])
        grouped[key]["published_years"] += scope["published_years"]
    return {key: dict(value) for key, value in sorted(grouped.items())}
