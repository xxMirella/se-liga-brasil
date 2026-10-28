"""Independently bridge an ALERJ public name to a verified civil identity."""

from crawlers.alerj.historical_parsing import parse_historical_profile
from database.enrichment import match_official_person
from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError


def verify_historical_identity(connection, person_id, profile_bytes, bridge_document):
    profile = parse_historical_profile(profile_bytes)
    try:
        senator = bridge_document["DetalheParlamentar"]["Parlamentar"]
        identity = senator["IdentificacaoParlamentar"]
        civil_name = identity["NomeCompletoParlamentar"]
        public_name = identity["NomeParlamentar"]
        birth_date = senator["DadosBasicosParlamentar"]["DataNascimento"]
    except (KeyError, TypeError) as error:
        raise IngestionError("ALERJ_HISTORICAL_IDENTITY_BRIDGE_INSUFFICIENT") from error
    if (
        normalize_person_name(public_name) != normalize_person_name(profile["displayName"])
        or birth_date != profile["birthDate"]
    ):
        raise IngestionError("ALERJ_HISTORICAL_IDENTITY_BRIDGE_MISMATCH")
    method = match_official_person(
        connection, {"nomeCivil": civil_name, "dataNascimento": birth_date}, person_id
    )
    return profile | {
        "civilName": civil_name,
        "identityMethod": method + ":official_public_name_bridge",
    }
