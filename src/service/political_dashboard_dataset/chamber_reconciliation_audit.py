"""Keep nominal uncertainty and electoral condition separate from exercise and office."""

from crawlers.camara.legacy_reconciliation import latest_affiliation_group
from service.political_dashboard.camara_orientation import chamber_orientation


def nominal_reconciliation_audit(histories, legislatures, members, uf_rows, year):
    indexed = {history["official_deputy_id"]: history for history in histories}
    active = next(identifier for identifier, bounds in legislatures.items()
                  if bounds["dataInicio"][:10] <= f"{year}-12-31" <= bounds["dataFim"][:10])
    bounds = legislatures[active]
    crosswalk = []
    for member in members:
        group = latest_affiliation_group(indexed[member["source_person_id"]]["events"],
                                         active, bounds, f"{year}-12-31")
        conditions = sorted({row["condicaoEleitoral"] for row in group
                             if row.get("condicaoEleitoral")})
        crosswalk.append({**member, "year": year, "office_kind": "federal_deputy",
                          "electoral_condition": conditions[0] if len(conditions) == 1 else None,
                          "electoral_condition_candidates": conditions,
                          "orientation": chamber_orientation(
                              {"abbreviation": member["political_party"]}, year,
                              identity_alignment=True,
                          )})
    deficient = {row["uf"] for row in uf_rows if row["unresolved"]}
    present = {member["source_person_id"] for member in members}
    pending = []
    for history in histories:
        identifier = history["official_deputy_id"]
        if identifier in present:
            continue
        group = latest_affiliation_group(history["events"], active, bounds, f"{year}-12-31")
        if not group or group[0].get("siglaUf") not in deficient:
            continue
        if group[0]["dataHora"][:10] < f"{year}-01-01":
            continue
        pending.append({"source_person_id": identifier, "name": group[0]["nome"],
                        "uf": group[0]["siglaUf"], "events": group,
                        "official_url": f"https://dadosabertos.camara.leg.br/api/v2/deputados/"
                                        f"{identifier}/historico"})
    return crosswalk, pending
