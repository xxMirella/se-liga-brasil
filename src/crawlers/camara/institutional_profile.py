"""A current roster and a full personal profile establish an observed office, not its start."""

from datetime import date

from normalization.scalars import normalize_text
from service.ingestion.contracts import IngestionError


def normalize_institutional_profile(document, member, observed_on):
    try:
        profile = document["dados"]
        status = profile["ultimoStatus"]
        code = str(profile["id"])
        birth = date.fromisoformat(profile["dataNascimento"])
        civil_name = normalize_text(profile["nomeCivil"], required=True)
        display_name = normalize_text(status["nome"], required=True)
        if code != str(member["id"]) or status["siglaUf"] != member["siglaUf"]:
            raise IngestionError("CAMARA_IDENTITY_ROSTER_MISMATCH")
        if birth >= date.fromisoformat(observed_on) or not code.isascii() or not code.isdigit():
            raise IngestionError("CAMARA_INSTITUTIONAL_IDENTITY_INSUFFICIENT")
    except (KeyError, TypeError, ValueError) as error:
        raise IngestionError("CAMARA_INSTITUTIONAL_IDENTITY_INSUFFICIENT") from error
    return {
        "personId": None,
        "civilName": civil_name,
        "displayName": display_name,
        "birthDate": birth.isoformat(),
        "educationLevel": profile.get("escolaridade"),
        "officialDeputyCode": code,
        "politicalPartyAbbreviation": status["siglaPartido"],
        "representedUf": status["siglaUf"],
        "institutionCode": "camara",
        "officeKind": "federal_deputy",
        "legislatureKey": str(status["idLegislatura"]),
        "inExercise": status.get("situacao") == "Exercício",
        "exerciseStartsOn": None,
        "termStart": None,
        "termEndExclusive": None,
        "capacity": "holder" if status.get("condicaoEleitoral") == "Titular" else "substitute",
        "observedOn": observed_on,
        "photoUrl": status.get("urlFoto"),
        "identityMethod": "validated_cpf_or_unique_full_name_birth_date",
    }
