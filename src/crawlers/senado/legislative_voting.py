"""Pure Senate voting normalization; collective decisions never imply personal votes."""

import re
from datetime import date

from service.ingestion.contracts import IngestionError

CHOICES = {
    "Sim": ("yes", "voted"),
    "Não": ("no", "voted"),
    "Abstenção": ("abstention", "voted"),
    "Obstrução": ("obstruction", "voted"),
    "Presidente": (None, "presiding"),
    "Pres": (None, "presiding"),
    "P-NRV": (None, "not_recorded"),
    "AP": (None, "parliamentary_activity"),
    "NCom": (None, "absent"),
    "Ausente": (None, "absent"),
    "LS": (None, "excused"),
}


def normalize_individual_vote(row):
    code = row.get("siglaVotoParlamentar")
    choice, status = CHOICES.get(code, (None, "unknown"))
    return {
        "voter_name": row.get("nomeParlamentar"),
        "represented_uf": row.get("siglaUFParlamentar"),
        "choice": choice,
        "participation_status": status,
        "source_choice_code": code,
        "description": row.get("descricaoVotoParlamentar"),
        "political_party_observed": row.get("siglaPartidoParlamentar"),
    }


def normalize_voting_record(row):
    required = ("codigoSessaoVotacao", "dataSessao", "idProcesso", "votacaoSecreta")
    if not isinstance(row, dict) or any(row.get(key) is None for key in required):
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    if row["votacaoSecreta"] not in {"S", "N"}:
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    secret = row["votacaoSecreta"] == "S"
    votes = [] if secret else row.get("votos", [])
    if not isinstance(votes, list) or any(not isinstance(vote, dict) for vote in votes):
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    report = row.get("informeLegislativo") or {}
    description = row.get("descricaoVotacao") or ""
    turn = re.search(r"\bem (primeiro|segundo|1[ºo]?|2[ºo]?) turno\b", description, re.I)
    round_number = (
        None if not turn else (1 if turn[1].lower() in {"primeiro", "1", "1º", "1o"} else 2)
    )
    return {
        "source_key": f"plenary:{row['codigoSessaoVotacao']}",
        "proposition_source_key": str(row["idProcesso"]),
        "proposition_kind": row.get("sigla") or "unknown",
        "proposition_number": row.get("numero"),
        "proposition_year": row.get("ano"),
        "proposition_title": row.get("identificacao") or description or "Objeto não informado",
        "occurred_on": date.fromisoformat(row["dataSessao"]).isoformat(),
        "date_precision": "day",
        "description": description,
        "body": row.get("casaSessao"),
        "legislative_body_code": report.get("siglaColegiado"),
        "session_key": str(row["codigoSessao"]) if row.get("codigoSessao") else None,
        "sequence_number": row.get("sequencialVotacao"),
        "round_number": round_number,
        "subject_kind": "unknown",
        "stage": "unknown",
        "collective_result_code": row.get("resultadoVotacao"),
        "final_outcome": None,
        "is_secret": secret,
        "method": "secret" if secret else "roll_call" if votes else "unknown",
        "nominal_availability": "secret" if secret else "published" if votes else "unavailable",
        "nominal_votes": [normalize_individual_vote(vote) for vote in votes],
        "totals": {
            key: row.get(key) for key in ("totalVotosSim", "totalVotosNao", "totalVotosAbstencao")
        },
    }


def resolve_voting_individuals(raw_rows, profile_index):
    resolved, unresolved = [], 0
    for row in raw_rows:
        if row["votacaoSecreta"] == "S":
            continue
        seen_people = set()
        for vote in row.get("votos", []):
            match = profile_index.get(str(vote.get("codigoParlamentar")))
            if match is None:
                unresolved += 1
                continue
            person_id, profile_hash = match
            if person_id in seen_people:
                raise IngestionError("DUPLICATE_SENATE_VOTER")
            seen_people.add(person_id)
            resolved.append(
                normalize_individual_vote(vote)
                | {
                    "voting_key": f"plenary:{row['codigoSessaoVotacao']}",
                    "person_id": person_id,
                    "identity_profile_sha256": profile_hash,
                    "identity_method": "unique_full_name_birth_date",
                }
            )
    return resolved, unresolved
