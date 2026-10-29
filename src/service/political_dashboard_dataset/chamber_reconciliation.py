"""Audit historical Chamber snapshots without manufacturing seats or substitution links."""

from collections import Counter
from datetime import date, timedelta

from crawlers.camara.legacy_reconciliation import (
    corroborated_historical_member,
    latest_affiliation_group,
)
from service.political_dashboard_dataset.camara_full_history import historical_source_member


def supplement_historical_members(members, histories, records, legislatures, identities,
                                  manifests, year):
    existing = {member["source_person_id"] for member in members}
    reconciled = []
    for history in histories:
        identifier = history["official_deputy_id"]
        if identifier in existing:
            continue
        corroboration = corroborated_historical_member(history, records, legislatures, year)
        if corroboration is None:
            continue
        group, period, evidence = corroboration
        member = historical_source_member(history, group[0], identities, manifests)
        member["exercise_source_sha256"] = evidence["sha256"]
        members.append(member)
        existing.add(identifier)
        reconciled.append({"source_person_id": identifier, "name": member["name"],
                           "uf": member["uf"], "political_party": member["political_party"],
                           "rest_events": group, "legacy_period": period,
                           "evidence": evidence})
    return reconciled


def verified_historical_vacancies(histories, records, legislatures, members, seats, year):
    indexed = {history["official_deputy_id"]: history for history in histories}
    reference = date(year, 12, 31)
    vacancies = {}
    for (successor, legislature), record in records.items():
        for period in record["periods"]:
            if not reference < period["starts_on"] <= reference + timedelta(days=31):
                continue
            predecessor = period["previous_source_person_id"]
            if predecessor not in indexed or successor not in indexed:
                continue
            vacancy = corroborated_vacancy(indexed, predecessor, successor, legislature,
                                           legislatures, period, record, reference)
            if vacancy:
                vacancies[predecessor] = vacancy
    counts = Counter(member["uf"] for member in members)
    vacant_counts = Counter(row["uf"] for row in vacancies.values())
    if any(counts[uf] + vacant_counts[uf] > capacity for uf, capacity in seats.items()):
        raise ValueError("CHAMBER_RECONCILED_VACANCIES_EXCEED_UF_CAPACITY")
    return list(vacancies.values())


def corroborated_vacancy(indexed, predecessor, successor, legislature, legislatures,
                        period, record, reference):
    group = latest_affiliation_group(indexed[predecessor]["events"], legislature,
                                     legislatures[legislature], str(reference))
    if not group or any(row.get("situacao") != "VACANCIA" for row in group):
        return None
    if any(row.get("siglaUf") != period["uf"] for row in group):
        return None
    entries = [event for event in indexed[successor]["events"]
               if event.get("idLegislatura") == legislature
               and event["dataHora"][:10] == str(period["starts_on"])
               and event.get("situacao") == "Exercício"
               and event.get("siglaUf") == period["uf"]
               and str(event.get("descricaoStatus", "")).startswith("Entrada - ")]
    if not entries:
        return None
    return {"uf": period["uf"], "vacant_on": str(reference),
            "departed_source_person_id": predecessor, "successor_source_person_id": successor,
            "departure_recorded_at": group[0]["dataHora"],
            "successor_assumed_at": min(event["dataHora"] for event in entries),
            "link_basis": "official_legacy_idCadastroParlamentarAnterior",
            "legacy_evidence": record["evidence"],
            "source_urls": [f"https://dadosabertos.camara.leg.br/api/v2/deputados/{identifier}"
                            "/historico" for identifier in (predecessor, successor)]}


def reconciliation_by_uf(members, vacancies, seats):
    counts = Counter(member["uf"] for member in members)
    vacant_counts = Counter(row["uf"] for row in vacancies)
    result = []
    for uf, capacity in sorted(seats.items()):
        unresolved = capacity - counts[uf] - vacant_counts[uf]
        if unresolved < 0:
            raise ValueError("CHAMBER_EXERCISE_EXCEEDS_UF_CAPACITY")
        result.append({"uf": uf, "expected_seats": capacity, "observed_people": counts[uf],
                       "documented_vacancies": vacant_counts[uf], "unresolved": unresolved})
    return result
