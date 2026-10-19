"""Pure row normalization. No network, filesystem or database dependencies."""

import re
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from crawlers.tse.configuration import UFS
from normalization.scalars import (
    normalize_boolean,
    normalize_date,
    normalize_digits,
    normalize_money,
    normalize_text,
    normalize_timestamp,
    normalize_year,
)
from service.ingestion.contracts import IngestionError, Resource
from storage.files import hash_content

REQUIRED_HEADERS = {
    "candidate": {
        "ANO_ELEICAO",
        "CD_ELEICAO",
        "SQ_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "CD_CARGO",
        "DS_CARGO",
        "SG_UF",
        "NR_TURNO",
        "DT_GERACAO",
        "HH_GERACAO",
    },
    "complement": {"ANO_ELEICAO", "CD_ELEICAO", "SQ_CANDIDATO", "DT_GERACAO", "HH_GERACAO"},
    "asset": {
        "ANO_ELEICAO",
        "CD_ELEICAO",
        "SQ_CANDIDATO",
        "NR_ORDEM_BEM_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "SG_UF",
        "DT_GERACAO",
        "HH_GERACAO",
    },
    "history": {
        "ANO_ELEICAO_ATUAL",
        "SQ_CANDIDATO_ATUAL",
        "ANO_ELEICAO",
        "SQ_CANDIDATO",
        "CD_ELEICAO",
        "NR_TURNO",
        "SG_UF",
        "SG_UF_ATUAL",
        "CD_CARGO",
        "DS_CARGO",
        "NM_CANDIDATO",
        "DT_GERACAO",
        "HH_GERACAO",
    },
}


def normalize_election_year(value) -> int:
    return normalize_year(value, minimum=1945, maximum=2200)


def normalize_uf(value) -> str:
    uf = normalize_text(value, required=True)
    if uf not in UFS:
        raise IngestionError("INVALID_UF")
    return uf


def normalize_generation_timestamp(row: dict) -> str:
    generated_date = normalize_date(row.get("DT_GERACAO"))
    generated_time = normalize_text(row.get("HH_GERACAO"), required=True)
    if not generated_date or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d", generated_time):
        raise IngestionError("INVALID_GENERATION_TIMESTAMP")
    timestamp = datetime.fromisoformat(f"{generated_date}T{generated_time}")
    timestamp = timestamp.replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(UTC)
    if timestamp > datetime.now(UTC) + timedelta(days=1):
        raise IngestionError("FUTURE_GENERATION_TIMESTAMP")
    return timestamp.isoformat()


def normalize_candidate(row: dict) -> dict:
    election_round = int(normalize_digits(row.get("NR_TURNO")))
    if not 1 <= election_round <= 3:
        raise IngestionError("INVALID_ELECTION_ROUND")
    birth_date = normalize_date(row.get("DT_NASCIMENTO"))
    if birth_date and not "1850-01-01" <= birth_date <= date.today().isoformat():
        raise IngestionError("INVALID_BIRTH_DATE")
    civil_name = normalize_text(row.get("NM_CANDIDATO"), required=True)
    return {
        "electionYear": normalize_election_year(row.get("ANO_ELEICAO")),
        "electionId": normalize_digits(row.get("CD_ELEICAO")),
        "candidateSequence": normalize_digits(row.get("SQ_CANDIDATO")),
        "electionRound": election_round,
        "representedUf": normalize_uf(row.get("SG_UF")),
        "officeCode": normalize_digits(row.get("CD_CARGO")),
        "officeName": normalize_text(row.get("DS_CARGO"), required=True),
        "civilName": civil_name,
        "displayName": normalize_text(row.get("NM_URNA_CANDIDATO")) or civil_name,
        "birthDate": birth_date,
        "educationLevel": normalize_text(row.get("DS_GRAU_INSTRUCAO")),
        "politicalPartyCode": normalize_digits(row.get("NR_PARTIDO"), required=True),
        "politicalPartyName": normalize_text(row.get("NM_PARTIDO"), required=True),
        "politicalPartyAbbreviation": normalize_text(row.get("SG_PARTIDO"), required=True),
        "candidacyStatus": normalize_text(row.get("DS_SITUACAO_CANDIDATURA")),
        "electionResult": normalize_text(row.get("DS_SIT_TOT_TURNO")),
    }


def normalize_history(row: dict) -> dict:
    return normalize_candidate(row) | {
        "anchorYear": normalize_election_year(row.get("ANO_ELEICAO_ATUAL")),
        "anchorCandidateSequence": normalize_digits(row.get("SQ_CANDIDATO_ATUAL")),
        "anchorUf": normalize_uf(row.get("SG_UF_ATUAL")),
    }


def normalize_asset(row: dict) -> dict:
    declared_value = normalize_money(
        row.get("VR_BEM_CANDIDATO"), required=True, allow_negative=True
    )
    data = {
        "electionYear": normalize_election_year(row.get("ANO_ELEICAO")),
        "electionId": normalize_digits(row.get("CD_ELEICAO")),
        "candidateSequence": normalize_digits(row.get("SQ_CANDIDATO")),
        "assetOrder": normalize_digits(row.get("NR_ORDEM_BEM_CANDIDATO")),
        "assetType": normalize_text(row.get("DS_TIPO_BEM_CANDIDATO"))
        or normalize_digits(row.get("CD_TIPO_BEM_CANDIDATO")),
        "description": normalize_text(row.get("DS_BEM_CANDIDATO")),
        "declaredValue": declared_value,
        "representedUf": normalize_uf(row.get("SG_UF")),
    }

    if declared_value.startswith("-"):
        data["declaredValueQuality"] = "negative_requires_review"
    return data


COMPLEMENT_TEXT_FIELDS = {
    "birthMunicipality": "NM_MUNICIPIO_NASCIMENTO",
    "nationality": "DS_NACIONALIDADE",
    "judgmentStatus": "DS_SITUACAO_JULGAMENTO",
    "diplomaStatus": "DS_SITUACAO_DIPLOMA",
    "revocationStatus": "DS_SITUACAO_CASSACAO",
    "electionStatus": "DS_SITUACAO_CANDIDATO_PLEITO",
    "ballotStatus": "DS_SITUACAO_CANDIDATO_URNA",
    "countingStatus": "DS_SITUACAO_CANDIDATO_TOT",
}


def normalize_complement(row: dict) -> dict:
    text_fields = {
        name: normalize_text(row.get(column)) for name, column in COMPLEMENT_TEXT_FIELDS.items()
    }
    return text_fields | {
        "electionYear": normalize_election_year(row.get("ANO_ELEICAO")),
        "electionId": normalize_digits(row.get("CD_ELEICAO")),
        "candidateSequence": normalize_digits(row.get("SQ_CANDIDATO")),
        "campaignSpendingLimit": normalize_money(
            row.get("VR_DESPESA_MAX_CAMPANHA"), decimal_separator="."
        ),
        "reelectionDeclared": normalize_boolean(row.get("ST_REELEICAO")),
        "declaresAssets": normalize_boolean(row.get("ST_DECLARAR_BENS")),
        "substituted": normalize_boolean(row.get("ST_SUBSTITUIDO")),
        "substituteSequence": normalize_digits(row.get("SQ_SUBSTITUIDO"), required=False),
        "candidacyAcceptedAt": normalize_timestamp(
            row.get("DT_ACEITE_CANDIDATURA"), time_zone=ZoneInfo("America/Sao_Paulo")
        ),
        "caseNumber": normalize_digits(row.get("NR_PROCESSO"), required=False),
        "candidacyProtocol": normalize_digits(row.get("NR_PROTOCOLO_CANDIDATURA"), required=False),
    }


NORMALIZERS = {
    "candidate": normalize_candidate,
    "history": normalize_history,
    "asset": normalize_asset,
    "complement": normalize_complement,
}


def build_external_key(data: dict, kind: str) -> str:
    key = f"{data['electionYear']}:{data['electionId']}:{data['candidateSequence']}"
    if kind in {"candidate", "history"}:
        key += f":{data['electionRound']}"
    if kind == "history":
        key = f"{data['anchorYear']}:{data['anchorCandidateSequence']}:{key}"
    if kind == "asset":
        key += f":{data['assetOrder']}"
    return key


def normalize_row(row: dict, resource: Resource, *, entry_name: str, row_number: int) -> dict:
    data = NORMALIZERS[resource.kind](row)
    dataset_year = data.get("anchorYear", data["electionYear"])
    if dataset_year != resource.year:
        raise IngestionError("DATASET_YEAR_MISMATCH")
    return {
        "kind": resource.kind,
        "externalKey": build_external_key(data, resource.kind),
        "normalizedData": data,
        "contentSha256": hash_content(data),
        "sourceGeneratedAt": normalize_generation_timestamp(row),
        "entryName": entry_name,
        "rowNumber": row_number,
    }
