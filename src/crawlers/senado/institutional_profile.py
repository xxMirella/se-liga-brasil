"""Validate national roster profiles independently from electoral candidacies."""

from datetime import date

from crawlers.senado.normalization import normalize_profile
from service.ingestion.contracts import IngestionError


def normalize_institutional_profile(document, member, observed_on):
    try:
        profile = document["DetalheParlamentar"]["Parlamentar"]
        identification = profile["IdentificacaoParlamentar"]
        roster_identity = member["IdentificacaoParlamentar"]
        code = str(identification["CodigoParlamentar"])
        birth = profile["DadosBasicosParlamentar"]["DataNascimento"]
        civil_name = identification["NomeCompletoParlamentar"].strip()
        display_name = identification["NomeParlamentar"].strip()
        birth_date = date.fromisoformat(birth)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise IngestionError("SENATE_INSTITUTIONAL_IDENTITY_INSUFFICIENT") from error
    if not code.isascii() or not code.isdigit() or int(code) <= 0:
        raise IngestionError("SENATE_INSTITUTIONAL_IDENTITY_INSUFFICIENT")
    if code != str(roster_identity["CodigoParlamentar"]):
        raise IngestionError("SENATE_IDENTITY_PROFILE_KEY_MISMATCH")
    if not civil_name or not display_name or birth_date >= date.fromisoformat(observed_on):
        raise IngestionError("SENATE_INSTITUTIONAL_IDENTITY_INSUFFICIENT")
    normalized = normalize_profile(
        profile, member, None, "unique_full_name_birth_date", observed_on
    )
    return normalized | {
        "civilName": civil_name,
        "displayName": display_name,
        "officialSenatorCode": code,
    }
