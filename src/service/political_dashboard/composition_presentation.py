"""Present snapshots and historical lists consistently without promoting lists into seat counts."""

from collections import Counter

UNKNOWN_AFFILIATION = "Filiação histórica não verificada"


def composition_presentation(composition):
    if composition.get("total"):
        partial_cohort = composition.get("aggregation_basis") == (
            "verified_year_end_status_of_current_roster_cohort"
        )
        label = (
            "parlamentares da composição atual documentados neste ano · histórico parcial"
            if partial_cohort else "pessoas em exercício na composição observada"
        )
        if composition.get("aggregation_basis") == (
            "verified_year_end_status_of_historical_legislature_rosters"
        ):
            label = "parlamentares documentados neste ano · histórico parcial"
        if composition.get("aggregation_basis") == (
            "official_active_legislature_registry_not_individual_exercise_confirmation"
        ):
            label = "registros ativos na legislatura observada"
        if composition.get("aggregation_basis") == (
            "official_roster_reconciled_with_dated_exercise_evidence"
        ):
            label = "registros conciliados com evidências datadas"
        return dict(composition, presentation_basis="snapshot", count_label=label)
    if composition.get("historical_roster"):
        members = historical_members(composition["historical_roster"])
        basis, label = "historical_roster", "integrantes documentados no período"
    else:
        members = composition.get("members", [])
        basis, label = "annual_members", "integrantes documentados no ano"
    counts = Counter(member.get("political_party") or UNKNOWN_AFFILIATION for member in members)
    return dict(
        composition,
        total=len(members),
        members=members,
        political_parties=[
            {"abbreviation": name, "count": count} for name, count in sorted(counts.items())
        ],
        presentation_basis=basis if members else "empty",
        count_label=label,
    )


def historical_members(rows):
    members = {}
    for row in rows:
        key = row.get("source_person_id") or row.get("person_id") or (row["name"], row.get("uf"))
        member = members.setdefault(
            key,
            dict(
                row, political_party=UNKNOWN_AFFILIATION, legislatures=set(), represented_ufs=set()
            ),
        )
        member["legislatures"].add(str(row["legislature"]))
        if row.get("uf"):
            member["represented_ufs"].add(row["uf"])
    for member in members.values():
        member["uf"] = " / ".join(sorted(member["represented_ufs"]))
        member["period_description"] = "Legislaturas: " + ", ".join(sorted(member["legislatures"]))
    return sorted(members.values(), key=lambda row: row["name"])
