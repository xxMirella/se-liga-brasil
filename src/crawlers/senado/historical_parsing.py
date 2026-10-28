"""Reconstruct only exercises and affiliations supported by dated Senate records."""

from datetime import date

from crawlers.senado.historical_party_names import historical_senate_political_party


def source_items(value):
    return value if isinstance(value, list) else [value] if value else []


def parse_legislature_roster(payload, legislature, evidence):
    """A historical roll proves listing for a legislature, not a simultaneous seat."""
    root = payload["ListaParlamentarLegislatura"]
    result = []
    for person in source_items((root.get("Parlamentares") or {}).get("Parlamentar")):
        identity = person["IdentificacaoParlamentar"]
        for mandate in source_items((person.get("Mandatos") or {}).get("Mandato")):
            periods = [mandate[key] for key in (
                "PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato"
            ) if mandate.get(key, {}).get("NumeroLegislatura") == str(legislature)]
            if not periods:
                continue
            result.append({
                "source_person_id": str(identity["CodigoParlamentar"]),
                "name": identity["NomeParlamentar"], "uf": mandate["UfParlamentar"],
                "legislature": legislature,
                "period_start": min(period["DataInicio"] for period in periods),
                "period_end": max(period["DataFim"] for period in periods),
                "official_url": evidence["url"], "evidence": evidence,
            })
    return result


def parse_exercises(payload, evidence):
    root = payload["ListaParlamentarLegislatura"]
    result = []
    for person in source_items((root.get("Parlamentares") or {}).get("Parlamentar")):
        identity = person["IdentificacaoParlamentar"]
        for mandate in source_items((person.get("Mandatos") or {}).get("Mandato")):
            result.extend(parse_mandate_exercises(identity, mandate, evidence))
    return result


def parse_mandate_exercises(identity, mandate, evidence):
    periods = [mandate[key] for key in (
        "PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato"
    ) if mandate.get(key)]
    mandate_end = max((period["DataFim"] for period in periods), default=None)
    result = []
    for exercise in source_items((mandate.get("Exercicios") or {}).get("Exercicio")):
        start = exercise.get("DataInicio")
        if not start:
            continue
        end = exercise.get("DataFim") or mandate_end
        date.fromisoformat(start)
        if end:
            date.fromisoformat(end)
            if end < start:
                raise ValueError("SENATE_EXERCISE_REVERSED_INTERVAL")
        result.append({
            "source_person_id": str(identity["CodigoParlamentar"]),
            "name": identity["NomeParlamentar"],
            "civil_name": identity.get("NomeCompletoParlamentar"),
            "uf": mandate["UfParlamentar"],
            "exercise_id": str(exercise["CodigoExercicio"]),
            "mandate_id": str(mandate["CodigoMandato"]),
            "starts_on": start, "ends_on": end,
            "capacity": mandate.get("DescricaoParticipacao"), "evidence": evidence,
        })
    return result


def parse_affiliations(payload, source_person_id, evidence):
    person = (payload.get("FiliacaoParlamentar") or {}).get("Parlamentar") or {}
    if str(person.get("Codigo")) != str(source_person_id):
        raise ValueError("SENATE_AFFILIATION_PERSON_MISMATCH")
    result = []
    for row in source_items((person.get("Filiacoes") or {}).get("Filiacao")):
        if not row.get("DataFiliacao"):
            continue
        date.fromisoformat(row["DataFiliacao"])
        if row.get("DataDesfiliacao"):
            date.fromisoformat(row["DataDesfiliacao"])
        result.append({
            "starts_on": row["DataFiliacao"], "ends_on": row.get("DataDesfiliacao"),
            "code": str(row["Partido"]["CodigoPartido"]),
            "abbreviation": row["Partido"]["SiglaPartido"], "evidence": evidence,
        })
    return result


def contains_reference(interval, reference):
    return interval["starts_on"] <= reference and (
        not interval.get("ends_on") or interval["ends_on"] >= reference
    )


def annual_senate_observations(exercises, affiliations, year):
    reference = f"{year}-12-31"
    selected = {}
    for exercise in exercises:
        if not contains_reference(exercise, reference):
            continue
        code = exercise["source_person_id"]
        if code in selected and selected[code]["uf"] != exercise["uf"]:
            raise ValueError("SENATE_CONCURRENT_DIFFERENT_TERRITORIES")
        selected[code] = exercise
    return [annual_senate_observation(row, affiliations.get(code, []), reference)
            for code, row in sorted(selected.items())]


def annual_senate_observation(exercise, affiliations, reference):
    matches = [row for row in affiliations if contains_reference(row, reference)]
    identities = {(row["code"], row["abbreviation"]) for row in matches}
    affiliation = matches[0] if len(identities) == 1 else {}
    name, name_evidence = historical_senate_political_party(affiliation, reference)
    return {
        "person_id": "senado:" + exercise["source_person_id"],
        "display_name": exercise["name"], "institution_code": "senado",
        "observed_on": reference,
        "source_record_id": "senado:exercicio:" + exercise["exercise_id"],
        "observation": {
            "inExercise": True, "representedUf": exercise["uf"],
            "officeKind": "senator", "capacity": exercise["capacity"],
            "politicalPartyCode": "senado:" + affiliation["code"] if name else None,
            "politicalPartyAbbreviation": name,
        },
        "evidence": [exercise["evidence"]] + [row["evidence"] for row in matches]
        + ([name_evidence] if name_evidence else []),
    }
