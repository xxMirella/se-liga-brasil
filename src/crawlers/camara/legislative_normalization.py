"""Source-specific legislative facts; collective decisions never imply final enactment."""

from datetime import datetime

from crawlers.camara.normalization import normalize_proposition
from service.ingestion.contracts import IngestionError
from storage.files import hash_content


def normalize_legislative_detail(row):
    normalized = normalize_proposition(row, None)
    normalized.pop("personId")
    normalized.pop("role")
    normalized.pop("roleScope")
    normalized["recordKey"] = "detail:" + row["uri"]
    status = row.get("statusProposicao") or {}
    normalized["officialStatus"] = {
        key: value for key, value in status.items() if key != "uriUltimoRelator"
    }
    normalized["finalNormReference"] = row.get("urnFinal")
    normalized["principalProposition"] = row.get("uriPropPrincipal")
    return normalized


def normalize_proceeding(row, proposition_key):
    occurred_at = row.get("dataHora")
    sequence = row.get("sequencia")
    if not occurred_at or sequence is None:
        raise IngestionError("CAMARA_PROCEEDING_SCHEMA_CHANGED")
    try:
        timestamp = datetime.fromisoformat(occurred_at)
    except ValueError as error:
        raise IngestionError("CAMARA_PROCEEDING_INVALID_DATE") from error
    return {
        "officialKey": proposition_key,
        "recordKey": "proceeding:" + proposition_key + ":" + str(sequence),
        "eventKey": str(sequence),
        "occurredAt": timestamp.isoformat(),
        "timeZone": "America/Sao_Paulo",
        "eventType": "official_proceeding",
        "description": row.get("despacho") or row.get("descricaoTramitacao") or "",
        "organ": row.get("siglaOrgao"),
        "proceedingType": row.get("descricaoTramitacao"),
        "officialSituation": row.get("descricaoSituacao"),
        "proceedingCode": row.get("codTipoTramitacao"),
        "situationCode": row.get("codSituacao"),
        "documentUrl": row.get("url"),
        "status": "unknown",
    }


def normalize_author(row, proposition_key, resolve_person):
    person_id = resolve_person(row)
    if person_id is None:
        return None
    proponent = row.get("proponente")
    if proponent not in (0, 1, "0", "1"):
        raise IngestionError("CAMARA_AUTHOR_ROLE_UNVERIFIED")
    role = "author" if proponent in (1, "1") else "coauthor"
    return {
        "officialKey": proposition_key,
        "personId": str(person_id),
        "role": role,
        "signatureOrder": row.get("ordemAssinatura"),
        "recordKey": hash_content([proposition_key, str(person_id), role]),
    }


def normalize_collective_decision(row, proposition_key):
    if not row.get("uri") or not row.get("data"):
        raise IngestionError("CAMARA_VOTING_SCHEMA_CHANGED")
    return {
        "officialKey": proposition_key,
        "recordKey": row["uri"],
        "eventKey": "voting:" + row["uri"],
        "eventType": "collective_stage_decision",
        "occurredAt": row["data"] + "T00:00:00",
        "datePrecision": "day",
        "votingUrl": row["uri"],
        "occurredOn": row["data"],
        "recordedAt": row.get("dataHoraRegistro"),
        "organ": row.get("siglaOrgao"),
        "description": row.get("descricao"),
        "approvalIndicator": row.get("aprovacao"),
        "result": "approved" if row.get("aprovacao") == 1 else "unknown",
        "objectProposition": row.get("uriProposicaoObjeto"),
        "scope": "collective_stage_decision_not_final_project_result",
    }
