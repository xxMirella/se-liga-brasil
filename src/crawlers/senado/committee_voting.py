"""Verified committee contract; meeting timestamps are not voting timestamps."""

import re
from datetime import datetime
from urllib.parse import urlencode

from crawlers.senado.legislative import validate_interval
from crawlers.senado.legislative_voting import normalize_individual_vote
from normalization.scalars import normalize_digits, normalize_text
from service.ingestion.contracts import IngestionError


def committee_voting_rows(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("VotacoesComissao"), dict):
        raise IngestionError("SENATE_COMMITTEE_VOTING_SCHEMA_CHANGED")
    envelope = payload["VotacoesComissao"]
    metadata = envelope.get("Metadados")
    if not isinstance(metadata, dict) or metadata.get("VersaoServico") not in {"1", 1}:
        raise IngestionError("SENATE_COMMITTEE_VOTING_VERSION_CHANGED")
    container = envelope.get("Votacoes")
    if container is None:
        return [], "not_published_in_response"
    if not isinstance(container, dict):
        raise IngestionError("SENATE_COMMITTEE_VOTING_SCHEMA_CHANGED")
    rows = container.get("Votacao", [])
    rows = rows if isinstance(rows, list) else [rows]
    if any(not isinstance(row, dict) for row in rows):
        raise IngestionError("SENATE_COMMITTEE_VOTING_SCHEMA_CHANGED")
    return rows, "records_returned" if rows else "not_published_in_response"


def committee_vote_rows(row):
    container = row.get("Votos")
    if container is None:
        return []
    if not isinstance(container, dict):
        raise IngestionError("SENATE_COMMITTEE_PERSON_VOTE_SCHEMA_CHANGED")
    rows = container.get("Voto", [])
    rows = rows if isinstance(rows, list) else [rows]
    if any(not isinstance(vote, dict) for vote in rows):
        raise IngestionError("SENATE_COMMITTEE_PERSON_VOTE_SCHEMA_CHANGED")
    return rows


def normalize_committee_individual_vote(row):
    code = normalize_text(row.get("QualidadeVoto"), max_length=50)
    normalized_code = {"S": "Sim", "N": "Não"}.get(code, "unknown")
    vote = normalize_individual_vote(
        {
            "nomeParlamentar": row.get("NomeParlamentar"),
            "siglaPartidoParlamentar": row.get("SiglaPartidoParlamentar"),
            "siglaVotoParlamentar": normalized_code,
        }
    )
    president = row.get("VotoPresidente")
    if not isinstance(president, (str, bool, int, type(None))):
        raise IngestionError("SENATE_COMMITTEE_PRESIDING_FLAG_CHANGED")
    if president not in {None, "true", "false", "1", "0", True, False}:
        raise IngestionError("SENATE_COMMITTEE_PRESIDING_FLAG_CHANGED")
    return vote | {
        "source_choice_code": code,
        "is_presiding": None if president is None else president in {"true", "1", True},
        "parliamentary_house": normalize_text(row.get("SiglaCasaParlamentar"), max_length=10),
    }


def optional_total(value):
    text = normalize_digits(value, required=False)
    return int(text) if text is not None else None


def committee_proposition_reference(value):
    text = normalize_text(value, max_length=100)
    match = re.fullmatch(r"([A-Z][A-Z0-9-]{0,19})\s+([0-9]+)/([0-9]{4})", text or "")
    return None if not match else {"kind": match[1], "number": match[2], "year": int(match[3])}


def committee_event_identity(row):
    voting_key = normalize_digits(row.get("CodigoVotacao"))
    body_key = normalize_digits(row.get("CodigoColegiado"))
    house = normalize_text(row.get("SiglaCasaColegiado"), required=True, max_length=10)
    return {
        "source_key": f"committee:{house}:{body_key}:{voting_key}",
        "body": house,
        "legislative_body_key": body_key,
    }


def normalize_committee_voting(row):
    timestamp = normalize_text(row.get("DataHoraInicioReuniao"), max_length=50)
    try:
        meeting_date = datetime.fromisoformat(timestamp).date().isoformat() if timestamp else None
    except ValueError as error:
        raise IngestionError("INVALID_COMMITTEE_MEETING_START") from error
    votes = committee_vote_rows(row)
    return committee_event_identity(row) | {
        "proposition_source_key": None,
        "proposition_reference": committee_proposition_reference(row.get("IdentificacaoMateria")),
        "proposition_identification": normalize_text(row.get("IdentificacaoMateria")),
        "description": normalize_text(row.get("DescricaoVotacao")),
        "subject_kind": "unknown",
        "stage": "committee",
        "round_number": None,
        "legislative_body_code": normalize_text(row.get("SiglaColegiado")),
        "session_key": normalize_digits(row.get("CodigoReuniao"), required=False),
        "meeting_started_at_local": timestamp,
        "meeting_date": meeting_date,
        "occurred_on": None,
        "date_precision": "unknown",
        "date_reference": "meeting_start",
        "method": "roll_call" if votes else "unknown",
        "nominal_availability": "published" if votes else "unavailable",
        "collective_result_code": None,
        "final_outcome": None,
        "nominal_votes": [normalize_committee_individual_vote(vote) for vote in votes],
        "totals": {
            name: optional_total(row.get(field))
            for name, field in (
                ("yes", "TotalVotosSim"),
                ("no", "TotalVotosNao"),
                ("abstention", "TotalVotosAbstencao"),
            )
        },
    }


def collect_committee_votings(acquisition, committee_code, start, end, *, maximum=1000):
    validate_interval(start, end)
    if (
        (end - start).days >= 31
        or not isinstance(committee_code, str)
        or not re.fullmatch(r"[A-Z][A-Z0-9-]{0,19}", committee_code)
    ):
        raise IngestionError("INVALID_SENATE_COMMITTEE_VOTING_SCOPE")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 1000:
        raise IngestionError("INVALID_SENATE_COMMITTEE_VOTING_BUDGET")
    query = urlencode(
        {"dataInicio": start.strftime("%Y%m%d"), "dataFim": end.strftime("%Y%m%d"), "v": 1}
    )
    payload, artifact = acquisition.json_document(
        f"votacaoComissao/comissao/{committee_code}.json?{query}", "senado_committee_votings"
    )
    rows, publication_status = committee_voting_rows(payload)
    if len(rows) > maximum:
        raise IngestionError("SENATE_COMMITTEE_VOTING_RECORD_LIMIT_EXCEEDED")
    normalized = [normalize_committee_voting(row) for row in rows]
    validate_committee_scope(normalized, committee_code, start, end)
    coverage = {
        "publication_status": publication_status,
        "coverage": "not_verified",
        "exact_voting_dates": "not_published_in_contract",
        "votings": len(normalized),
    }
    return normalized, artifact, coverage


def validate_committee_scope(records, committee_code, start, end):
    seen = set()
    for row in records:
        if row["legislative_body_code"] != committee_code:
            raise IngestionError("SENATE_COMMITTEE_BODY_MISMATCH")
        meeting_date = row["meeting_date"]
        if meeting_date and not start.isoformat() <= meeting_date <= end.isoformat():
            raise IngestionError("SENATE_COMMITTEE_MEETING_OUTSIDE_PARTITION")
        if row["source_key"] in seen:
            raise IngestionError("DUPLICATE_SENATE_COMMITTEE_VOTING")
        seen.add(row["source_key"])


def resolve_committee_individuals(rows, profile_index):
    """Only Senate profiles resolve Senate voters; a mixed-house committee stays explicit."""
    resolved, missing = [], 0
    for row in rows:
        voting_key = committee_event_identity(row)["source_key"]
        seen_people = set()
        for vote in committee_vote_rows(row):
            match = profile_index.get(str(vote.get("CodigoParlamentar")))
            if vote.get("SiglaCasaParlamentar") != "SF" or match is None:
                missing += 1
                continue
            person_id, profile_hash = match
            if person_id in seen_people:
                raise IngestionError("DUPLICATE_SENATE_COMMITTEE_VOTER")
            seen_people.add(person_id)
            resolved.append(
                normalize_committee_individual_vote(vote)
                | {
                    "voting_key": voting_key,
                    "person_id": person_id,
                    "identity_profile_sha256": profile_hash,
                    "identity_method": "unique_full_name_birth_date",
                }
            )
    return resolved, missing
