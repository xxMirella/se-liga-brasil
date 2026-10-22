"""Normalize institutional observations without inventing electoral or legal facts."""

from datetime import date, timedelta

from normalization.scalars import normalize_text
from service.ingestion.contracts import IngestionError


def normalize_profile(profile, history, legislature, person_id, method) -> dict:
    status = profile["ultimoStatus"]
    legislature_id = status["idLegislatura"]
    if legislature.get("id") != legislature_id:
        raise IngestionError("CAMARA_LEGISLATURE_MISMATCH")
    events = [
        row for row in history if row.get("idLegislatura") == legislature_id and row.get("situacao")
    ]
    exercise_start = continuous_exercise_start(events)
    return {
        "personId": person_id,
        "civilName": normalize_text(profile["nomeCivil"], required=True),
        "displayName": normalize_text(status["nome"], required=True),
        "birthDate": profile.get("dataNascimento"),
        "educationLevel": profile.get("escolaridade"),
        "politicalPartyAbbreviation": status["siglaPartido"],
        "representedUf": status["siglaUf"],
        "legislatureKey": str(legislature_id),
        "termStart": legislature["dataInicio"],
        "termEndExclusive": (
            date.fromisoformat(legislature["dataFim"]) + timedelta(days=1)
        ).isoformat(),
        "exerciseStartsOn": exercise_start if status.get("situacao") == "Exercício" else None,
        "inExercise": status.get("situacao") == "Exercício" and exercise_start is not None,
        "capacity": "holder" if status.get("condicaoEleitoral") == "Titular" else "substitute",
        "identityMethod": method,
        "institutionCode": "camara",
        "photoUrl": status.get("urlFoto"),
        "history": [
            {
                key: row.get(key)
                for key in (
                    "dataHora",
                    "siglaPartido",
                    "situacao",
                    "condicaoEleitoral",
                    "descricaoStatus",
                )
            }
            for row in events
        ],
    }


def normalize_proposition(row, person_id) -> dict:
    required = ("uri", "siglaTipo")
    if any(row.get(key) is None for key in required):
        raise IngestionError("CAMARA_PROPOSITION_SCHEMA_CHANGED")
    year = int(row.get("ano") or 0) or None
    if year is not None and not 1800 <= year <= 2200:
        raise IngestionError("INVALID_PROPOSITION_YEAR")
    number = str(row["numero"]) if row.get("numero") is not None else None
    title = row["siglaTipo"] + (f" {number}" if number is not None else "")
    return {
        "personId": person_id,
        "officialKey": row["uri"],
        "kind": row["siglaTipo"],
        "number": number,
        "year": year,
        "title": title + (f"/{year}" if year is not None else ""),
        "summary": row.get("ementa"),
        "introducedOn": (row.get("dataApresentacao") or "")[:10] or None,
        "status": "unknown",
        "role": "author",
        "roleScope": "listed_by_official_author_filter_not_exclusive_authorship",
    }


def continuous_exercise_start(events):
    """Party/name updates do not restart exercise; explicit leave does."""
    by_timestamp = {}
    for event in events:
        timestamp = event["dataHora"]
        by_timestamp.setdefault(timestamp, set()).add(event["situacao"])
    start = None
    for timestamp in sorted(by_timestamp, reverse=True):
        states = by_timestamp[timestamp]
        if len(states) != 1:
            return None
        if states != {"Exercício"}:
            break
        start = timestamp[:10]
    return start
