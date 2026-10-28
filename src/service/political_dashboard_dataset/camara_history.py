"""Year-end snapshots for the explicitly incomplete cohort of today's federal deputies."""

from collections import defaultdict
from datetime import date, datetime

from crawlers.camara.historical_exercises import documented_year_end_status
from service.political_dashboard_dataset.aggregation import build_annual_partitions


def current_cohort_historical_partitions(histories, legislatures, identities, year):
    if not 2000 <= year < date.today().year:
        raise ValueError("HISTORICAL_CAMARA_YEAR_OUT_OF_RANGE")
    reference = date(year, 12, 31)
    observations = []
    evidence_by_territory = defaultdict(list)
    for history in histories:
        identity = identities.get(str(history["official_deputy_id"]))
        if identity is None:
            raise ValueError("UNVERIFIED_CAMARA_HISTORICAL_IDENTITY")
        if not history["evidence"] or reference > min(
            datetime.fromisoformat(item["fetched_at"]).date() for item in history["evidence"]
        ):
            continue
        status = documented_year_end_status(history["events"], legislatures, year)
        if status is None:
            continue
        observations.append(historical_observation(identity, status, reference))
        for territory in ("BR", status["siglaUf"]):
            evidence_by_territory[territory].extend(history["evidence"])
    partitions = build_annual_partitions(observations, year)
    for partition in partitions:
        partition["coverage"] = "observed_partial"
        partition["aggregation_basis"] = "verified_year_end_status_of_current_roster_cohort"
        partition["annual_cohort"] = "current_roster_only_not_all_historical_deputies"
        partition["cohort_people_with_history"] = len(histories)
        partition["evidence"] = evidence_by_territory[partition["territory_code"]]
    return partitions


def historical_observation(identity, status, reference):
    return {
        "person_id": identity["person_id"],
        "display_name": status["nome"],
        "source_record_id": identity["source_record_id"],
        "observed_on": reference,
        "institution_code": "camara",
        "observation": {
            "institutionCode": "camara",
            "officeKind": "federal_deputy",
            "inExercise": True,
            "politicalPartyAbbreviation": status["siglaPartido"],
            "politicalPartyCode": "camara:" + status["uriPartido"]
            if status.get("uriPartido")
            else None,
            "representedUf": status["siglaUf"],
            "observedOn": reference.isoformat(),
            "capacity": status.get("condicaoEleitoral"),
            "historicalPoliticalPartySourceUri": status.get("uriPartido"),
        },
    }
