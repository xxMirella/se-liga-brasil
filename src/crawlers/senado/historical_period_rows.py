"""Turn the validated plan into plain rows for set-based SQL; keys are stable across runs."""

from datetime import date
from uuid import NAMESPACE_DNS, UUID, uuid5

from crawlers.senado.historical_period_contracts import (
    LOAD_NAME,
    ArchivedDocument,
    SenateAffiliation,
    SenateParty,
    SenatorBundle,
)
from normalization.identity import normalize_person_name
from storage.files import hash_content

PERSON_NAMESPACE = uuid5(NAMESPACE_DNS, "se-liga-brasil.senado.historical-senator-identity")


def person_id_for(senator_id: str) -> UUID:
    """Opaque internal ID, derived from the official Senate ID so reruns cannot fork a person."""
    return uuid5(PERSON_NAMESPACE, senator_id)


def term_key(person_id, legislature_key: str) -> str:
    """Same convention as the current roster projection: person UUID + legislature pair."""
    return f"{person_id}:{legislature_key}"


DETAIL_IDENTIFICATION_FIELDS = (
    "CodigoParlamentar",
    "NomeParlamentar",
    "NomeCompletoParlamentar",
    "SexoParlamentar",
    "UrlPaginaParlamentar",
)
DETAIL_BASIC_FIELDS = ("DataNascimento", "Naturalidade", "UfNaturalidade")


def storable_payload(document: ArchivedDocument) -> dict:
    """The original bytes stay archived by hash; contact data is not copied into the database."""
    if document.kind != "detail":
        return document.payload
    profile = document.payload["DetalheParlamentar"]["Parlamentar"]
    identification = profile["IdentificacaoParlamentar"]
    basics = profile["DadosBasicosParlamentar"]
    return {
        "DetalheParlamentar": {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    key: identification[key]
                    for key in DETAIL_IDENTIFICATION_FIELDS
                    if key in identification
                },
                "DadosBasicosParlamentar": {
                    key: basics[key] for key in DETAIL_BASIC_FIELDS if key in basics
                },
            }
        }
    }


def document_record(document: ArchivedDocument) -> dict:
    return {
        "external_key": document.external_key,
        "source_url": document.url,
        "content_sha256": document.sha256,
        "fetched_at": document.fetched_at.isoformat(),
        "payload": storable_payload(document),
        "storage_reference": document.archive_path,
    }


def affiliation_key(affiliation: SenateAffiliation) -> str:
    return (
        f"{LOAD_NAME}:senator:{affiliation.senator_id}:affiliation:"
        f"{affiliation.senate_party_code}:{affiliation.starts_on}"
    )


def affiliation_record(affiliation: SenateAffiliation) -> dict:
    document = affiliation.document
    payload = {
        "senator_id": affiliation.senator_id,
        "filiacao": affiliation.raw_element,
        "archive": {"url": document.url, "sha256": document.sha256, "path": document.archive_path},
        "meaning": "senate_parliamentary_registration_not_civil_membership_certificate",
    }
    return {
        "external_key": affiliation_key(affiliation),
        "source_url": document.url,
        "content_sha256": hash_content(affiliation.raw_element),
        "fetched_at": document.fetched_at.isoformat(),
        "payload": payload,
        "storage_reference": document.archive_path,
    }


def party_record(party: SenateParty, catalog_document: ArchivedDocument) -> dict:
    element = {
        "Codigo": party.senate_party_code,
        "Sigla": party.abbreviation,
        "Nome": party.name,
        "DataCriacao": party.created_on.isoformat() if party.created_on else None,
        "DataExtincao": party.extinguished_on.isoformat() if party.extinguished_on else None,
    }
    return {
        "external_key": f"{LOAD_NAME}:party:{party.senate_party_code}",
        "source_url": catalog_document.url,
        "content_sha256": hash_content(element),
        "fetched_at": catalog_document.fetched_at.isoformat(),
        "payload": {
            "partido": element,
            "archive": {"sha256": catalog_document.sha256, "path": catalog_document.archive_path},
        },
        "storage_reference": catalog_document.archive_path,
    }


def qualified_abbreviation(party: SenateParty) -> str:
    """Disambiguates a historical abbreviation that another party row already uses."""
    end = party.extinguished_on.year if party.extinguished_on else ""
    start = party.created_on.year if party.created_on else "?"
    return f"{party.abbreviation} ({start}-{end})"


def name_birth_row(bundle: SenatorBundle) -> dict:
    identity = bundle.identity
    return {
        "senator_id": identity.senator_id,
        "normalized_name": normalize_person_name(identity.civil_name),
        "birth_date": identity.birth_date.isoformat(),
    }


def bundle_documents(bundle: SenatorBundle) -> list[ArchivedDocument]:
    documents = [bundle.identity.document, bundle.mandates_document, bundle.affiliations_document]
    return [document for document in documents if document is not None]


def date_text(value: date | None) -> str | None:
    return value.isoformat() if value else None
