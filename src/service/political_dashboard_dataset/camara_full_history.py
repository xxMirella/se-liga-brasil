"""Project only dated exercise status, with source-qualified identities for unlinked people."""

from collections import Counter, defaultdict
from datetime import date, datetime

from crawlers.camara.historical_exercises import documented_year_end_status
from service.political_dashboard_dataset.aggregation import build_annual_partition

FULL_HISTORY_BASIS = "verified_year_end_status_of_historical_legislature_rosters"
FULL_HISTORY_COHORT = "historical_legislatures_51_to_57_not_current_roster_only"


def historical_universe_members(histories, legislatures, identities, manifests, year):
    if not 2000 <= year < date.today().year:
        raise ValueError("HISTORICAL_CAMARA_YEAR_OUT_OF_RANGE")
    reference = f"{year}-12-31"
    members = []
    for history in histories:
        if reference > min(datetime.fromisoformat(row["fetched_at"]).date().isoformat()
                           for row in history["evidence"]):
            continue
        status = documented_year_end_status(history["events"], legislatures, year)
        if status:
            members.append(historical_source_member(history, status, identities, manifests))
    return members


def historical_source_member(history, status, identities, manifests):
    identifier = str(history["official_deputy_id"])
    identity = identities.get(identifier)
    return {
        "person_id": identity["person_id"] if identity else "camara:" + identifier,
        "source_person_id": identifier, "name": status["nome"],
        "political_party": status.get("siglaPartido") or "Filiação não informada",
        "uf": status["siglaUf"],
        "official_url": f"https://dadosabertos.camara.leg.br/api/v2/deputados/{identifier}/historico",
        "evidence_manifest_sha256": manifests[identifier],
    }


def historical_universe_partitions(members, year, people_archived, universe_people, manifest):
    groups = defaultdict(list)
    for member in members:
        groups["BR"].append(member)
        groups[member["uf"]].append(member)
    if len(groups.get("BR", [])) > 513:
        raise ValueError("CAMARA_HISTORICAL_STATUS_EXCEEDS_LEGAL_CAPACITY")
    return [historical_universe_partition(
        rows, year, territory, people_archived, universe_people, manifest,
    ) for territory, rows in sorted(groups.items())]


def historical_universe_partition(members, year, territory, archived, universe, manifest):
    partition = build_annual_partition([], year, territory, "camara")
    counts = Counter(row["political_party"] for row in members)
    complete = territory == "BR" and archived == universe and len(members) == 513
    if any(label in counts for label in ("Filiação não informada", "S/Partido")):
        complete = False
    reference = f"{year}-12-31"
    partition.update({
        "total": len(members), "seat_count": len(members), "observed_people_count": len(members),
        "observed_on": reference, "observed_from": reference, "snapshot_on": reference,
        "reference_on": reference, "date_precision": "day", "expected_seats": 513
        if territory == "BR" else None, "office_kinds": ["federal_deputy"],
        "coverage": "observed_complete" if complete else "observed_partial",
        "aggregation_basis": FULL_HISTORY_BASIS, "annual_cohort": FULL_HISTORY_COHORT,
        "historical_universe_people": universe, "cohort_people_with_history": archived,
        "coverage_detail": f"{archived} de {universe} históricos de pessoas arquivados; "
                           "contagem por situação de exercício datada. "
                           + ("Composição nominal integral verificada nesta data." if complete
                              else "Cobertura parcial de exercício e filiação nesta data."),
        "source_observation_count": len(members),
        "members": sorted(members, key=lambda member: member["name"]),
        "political_parties": [{"abbreviation": key, "count": value}
                              for key, value in sorted(counts.items())],
        "evidence": [{"url": "https://dadosabertos.camara.leg.br/swagger/api.html",
                      "source_kind": "derived_manifest_of_official_dated_status_archives",
                      "manifest_sha256": manifest,
                      "locator": "Históricos individuais e universo de legislaturas; "
                                 "proveniência individual identificada por manifesto SHA256"}],
    })
    return partition
