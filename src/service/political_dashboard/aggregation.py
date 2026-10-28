"""Aggregate dated observations without inferring unobserved party membership."""

from collections import Counter

from service.political_dashboard.contracts import ASSEMBLIES, HISTORY_START, STATE_NAMES


def observation_party(observation):
    return observation.get("politicalPartyAbbreviation") or "Filiação não informada"


def build_composition(rows, institution_code, represented_uf=None):
    institutional = [row for row in rows if row["institution_code"] == institution_code]
    observed_on = max((row["observed_on"] for row in institutional), default=None)
    members = {}
    for row in institutional:
        observation = row["observation"]
        if row["observed_on"] != observed_on or observation.get("inExercise") is not True:
            continue
        if represented_uf and observation.get("representedUf") != represented_uf:
            continue
        members[row["person_id"]] = {
            "person_id": row["person_id"],
            "name": row["display_name"],
            "political_party": observation_party(observation),
            "uf": observation.get("representedUf"),
            "capacity": observation.get("capacity"),
        }
    counts = Counter(member["political_party"] for member in members.values())
    return {
        "institution_code": institution_code,
        "observed_on": str(observed_on) if observed_on else None,
        "total": len(members),
        "coverage": "observed_partial" if members else "not_available",
        "political_parties": [
            {"abbreviation": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "members": sorted(members.values(), key=lambda member: member["name"]),
    }


def build_coverage_history(rows, query):
    observations = Counter(
        (row["institution_code"], row["observed_on"].year)
        for row in rows
        if row["institution_code"] in {"senado", ASSEMBLIES.get(query.uf)}
    )
    return [
        {
            "year": year,
            "senate_observations": observations["senado", year],
            "assembly_observations": observations[ASSEMBLIES.get(query.uf), year],
        }
        for year in range(HISTORY_START.year, query.as_of.year + 1)
    ]


def build_dashboard(rows, query):
    return {
        "uf": query.uf,
        "view": query.view,
        "level": query.level,
        "municipality_ibge": query.municipality_ibge,
        "municipalities": [],
        "presidency": {
            "coverage": "not_applicable" if query.year < 1889 else "not_available",
            "segments": [],
            "context_description": "O Brasil era uma monarquia. A Presidência começa em 1889.",
        },
        "federal_chamber": build_composition(rows, "camara", query.senate_uf),
        "municipal_council": build_composition(rows, None),
        "state_name": STATE_NAMES[query.uf],
        "as_of": str(query.as_of),
        "senate_uf": query.senate_uf,
        "senate": build_composition(rows, "senado", query.senate_uf),
        "assembly": build_composition(rows, ASSEMBLIES.get(query.uf)),
        "government": {"coverage": "not_available", "segments": []},
        "history": build_coverage_history(rows, query),
        "history_start": str(HISTORY_START),
    }
