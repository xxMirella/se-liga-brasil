"""Normalize explicit current Senate exercise without inferring from absence."""

from datetime import date, timedelta

from normalization.official_media import normalize_official_media_url
from service.ingestion.contracts import IngestionError


def as_list(value):
    return value if isinstance(value, list) else [value] if value else []


def current_members(document):
    try:
        rows = document["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
    except (KeyError, TypeError) as error:
        raise IngestionError("SENADO_CURRENT_ROSTER_SCHEMA_CHANGED") from error
    return as_list(rows)


def normalize_profile(profile, member, person_id, method, observed_on):
    identification = profile["IdentificacaoParlamentar"]
    mandate = member["Mandato"]
    first = mandate["PrimeiraLegislaturaDoMandato"]
    second = mandate["SegundaLegislaturaDoMandato"]
    exercises = as_list(mandate.get("Exercicios", {}).get("Exercicio"))
    active = [
        row
        for row in exercises
        if row["DataInicio"] <= observed_on
        and (not row.get("DataFim") or row["DataFim"] >= observed_on)
    ]
    if len(active) != 1:
        raise IngestionError("SENADO_EXERCISE_NOT_CONFIRMED")
    end = date.fromisoformat(second["DataFim"]) + timedelta(days=1)
    exercise_end = active[0].get("DataFim")
    exercise_end = (
        (date.fromisoformat(exercise_end) + timedelta(days=1)).isoformat() if exercise_end else None
    )
    return {
        "personId": person_id,
        "photoUrl": normalize_official_media_url(
            identification.get("UrlFotoParlamentar"),
            {"www.senado.leg.br", "senado.leg.br"},
            upgrade_http=True,
        ),
        "civilName": identification["NomeCompletoParlamentar"],
        "birthDate": profile["DadosBasicosParlamentar"]["DataNascimento"],
        "politicalPartyAbbreviation": identification.get("SiglaPartidoParlamentar"),
        "representedUf": mandate["UfParlamentar"],
        "identityMethod": method,
        "termStart": first["DataInicio"],
        "termEndExclusive": end.isoformat(),
        "legislatureKey": first["NumeroLegislatura"] + "-" + second["NumeroLegislatura"],
        "exerciseStartsOn": active[0]["DataInicio"],
        "exerciseEndExclusive": exercise_end,
        "capacity": "holder" if mandate["DescricaoParticipacao"] == "Titular" else "substitute",
        "inExercise": True,
        "observedOn": observed_on,
        "officeKind": "senator",
        "institutionCode": "senado",
    }
