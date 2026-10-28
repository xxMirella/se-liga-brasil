"""Map only selected annual partitions to the existing public dashboard contract."""

from collections import Counter, defaultdict

from service.political_dashboard.aggregation import build_dashboard
from service.political_dashboard.contracts import ASSEMBLIES, HISTORY_START


def annual_dashboard_payload(partitions, history, query, current_year=None):
    payload = build_dashboard([], query)
    indexed = {
        (entry["payload"]["territory_code"], entry["payload"]["institution_code"]): entry["payload"]
        for entry in partitions
    }
    senate_territory = query.uf if query.level == "state" else query.senate_uf or "BR"
    scopes = {
        "senate": (senate_territory, "senado"),
        "federal_chamber": (senate_territory, "camara"),
        "assembly": (query.uf, ASSEMBLIES.get(query.uf)),
        "presidency": ("BR", "presidency"),
        "government": (query.uf, "district_government" if query.uf == "DF" else "state_government"),
        "municipal_council": (query.municipality_ibge, "municipal_council"),
        "mayoralty": (query.municipality_ibge, "municipal_government"),
    }
    for name, key in scopes.items():
        if key in indexed:
            payload[name] = indexed[key]
    if payload["assembly"].get("coverage") == "not_available":
        for partition in indexed.values():
            if partition["territory_code"] == query.uf and set(
                partition.get("office_kinds", [])
            ) & {"state_deputy", "district_deputy"}:
                payload["assembly"] = partition
    payload["history"] = annual_history(history, query, current_year)
    payload.setdefault("mayoralty", {"coverage": "not_available", "segments": []})
    payload["year"] = query.as_of.year
    payload["annual_semantics"] = "observed_during_year_not_full_year_occupancy"
    payload["dataset_schema"] = "political_composition_annual.v1"
    return payload


def annual_history(rows, query, current_year=None):
    totals = {
        (row["year"], row["territory_code"], row["institution_code"]): row["total"]
        for row in rows
        if visible_history_institution(row, query)
    }
    assembly_totals = assembly_history_totals(rows, query)
    institutions = defaultdict(list)
    for row in rows:
        if visible_history_institution(row, query) and row.get("composition"):
            institutions[row["year"]].append(row["composition"])
    senate_territory = query.uf if query.level == "state" else query.senate_uf or "BR"
    annual_totals = Counter()
    for key, value in totals.items():
        annual_totals[key[0]] += value or 0
    return [
        {
            "year": year,
            "documented_records": annual_totals[year],
            "institutions": institutions[year],
            "senate_observations": totals.get((year, senate_territory, "senado"), 0),
            "assembly_observations": assembly_totals[year],
            "presidency_observations": totals.get((year, "BR", "presidency"), 0),
            "government_observations": totals.get(
                (year, query.uf, "district_government" if query.uf == "DF" else "state_government"),
                0,
            ),
            "mayoralty_observations": totals.get(
                (year, query.municipality_ibge, "municipal_government"), 0
            ),
            "municipal_council_observations": totals.get(
                (year, query.municipality_ibge, "municipal_council"), 0
            ),
        }
        for year in range(HISTORY_START.year, (current_year or query.as_of.year) + 1)
    ]


def selected_territories(query):
    if query.level == "state":
        return [query.uf]
    if query.level == "municipal":
        return [query.municipality_ibge] if query.municipality_ibge else []
    return list(dict.fromkeys(value for value in ["BR", query.senate_uf] if value))


def validate_municipality_catalog(query, catalog):
    from service.public_profile import PublicProfileError

    if not query.municipality_ibge:
        return
    if not catalog or not any(
        row["ibge_code"] == query.municipality_ibge for row in catalog["municipalities"]
    ):
        raise PublicProfileError("INVALID_DASHBOARD_MUNICIPALITY")


def visible_history_institution(row, query):
    institution = row["institution_code"]
    office_kinds = set(row.get("office_kinds") or [])
    if query.level == "federal":
        return institution in {"senado", "camara", "presidency"}
    if query.level == "state":
        return institution in {
            "senado",
            "state_government",
            "district_government",
            ASSEMBLIES.get(query.uf),
        } or bool(office_kinds & {"state_deputy", "district_deputy"})
    return institution in {"municipal_government", "municipal_council"} or bool(
        office_kinds & {"mayor", "councillor"}
    )


def assembly_history_totals(rows, query):
    unique = {}
    for row in rows:
        office_kinds = set(row.get("office_kinds") or [])
        if row["territory_code"] == query.uf and (
            row["institution_code"] == ASSEMBLIES.get(query.uf)
            or office_kinds & {"state_deputy", "district_deputy"}
        ):
            unique[row["year"], row["institution_code"]] = row["total"] or 0
    totals = Counter()
    for (year, _), count in unique.items():
        totals[year] += count
    return totals
