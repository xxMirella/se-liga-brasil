"""Incremental Senate process details using the current documented API."""

from datetime import date
from urllib.parse import urlencode

from service.ingestion.contracts import IngestionError

SUPPORTED_DOMAINS = frozenset({"propositions", "proceedings", "votings"})


def legislative_capability(domain, start, end):
    validate_interval(start, end)
    return {
        "institution": "senado",
        "domain": domain,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "status": "supported" if domain in SUPPORTED_DOMAINS else "unsupported",
        "source_coverage_start": None,
        "source_coverage_end": None,
        "historical_completeness": "not_verified",
    }


def validate_interval(start, end):
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise IngestionError("INVALID_LEGISLATIVE_INTERVAL")


def collect_process_details(acquisition, process_keys, max_processes=100):
    """Deduplicate before HTTP; provider process keys are never person identifiers."""
    keys = bounded_process_keys(process_keys, max_processes)
    for key in keys:
        payload, artifact = acquisition.json_document(f"processo/{key}.json?v=1", "process")
        normalized = normalize_process(payload)
        if normalized["source_key"] != str(key):
            raise IngestionError("SENATE_PROCESS_KEY_MISMATCH")
        yield normalized, artifact


def bounded_process_keys(process_keys, maximum):
    """Stop reading an oversized input before retaining it or making requests."""
    if not 1 <= maximum <= 100:
        raise IngestionError("INVALID_SENATE_PROCESS_SCOPE")
    keys = set()
    for value in process_keys:
        try:
            key = int(value)
        except (ValueError, TypeError) as error:
            raise IngestionError("INVALID_SENATE_PROCESS_SCOPE") from error
        if key <= 0:
            raise IngestionError("INVALID_SENATE_PROCESS_SCOPE")
        keys.add(key)
        if len(keys) > maximum:
            raise IngestionError("SENATE_PROCESS_BATCH_LIMIT_EXCEEDED")
    return sorted(keys)


def normalize_process(payload):
    if not isinstance(payload, dict) or not payload.get("id") or not payload.get("sigla"):
        raise IngestionError("SENATE_PROCESS_SCHEMA_CHANGED")
    document = payload.get("documento") or {}
    return {
        "source_key": str(payload["id"]),
        "document_url": document.get("url"),
        "kind": payload["sigla"],
        "number": payload.get("numero"),
        "year": payload.get("ano"),
        "presented_on": document.get("dataApresentacao"),
        "description": (payload.get("conteudo") or {}).get("ementa"),
        "current_status_description": payload.get("situacaoAtual"),
        "final_outcome": None,
        "events": list(process_events(payload)),
        "decision_evidence": payload.get("deliberacao") or None,
        "generated_norm_evidence": payload.get("normaGerada") or None,
        "authorship_evidence": document.get("autoria") or [],
    }


def process_events(payload):
    for proceeding in payload.get("autuacoes") or []:
        for report in proceeding.get("informesLegislativos") or []:
            if not report.get("id") or not report.get("data"):
                raise IngestionError("SENATE_PROCEEDING_SCHEMA_CHANGED")
            occurred_on = date.fromisoformat(report["data"][:10]).isoformat()
            body = report.get("colegiado") or report.get("enteAdministrativo") or {}
            yield {
                "source_key": str(report["id"]),
                "occurred_on": occurred_on,
                "event_kind": "proceeding",
                "description": report.get("descricao"),
                "body": body.get("sigla"),
                "final_outcome": None,
            }


def collect_votings(acquisition, start, end):
    """One bounded shared date partition, independent from the number of people."""
    validate_interval(start, end)
    if (end - start).days > 31:
        raise IngestionError("SENATE_VOTING_INTERVAL_LIMIT_EXCEEDED")
    query = urlencode({"dataInicio": start.isoformat(), "dataFim": end.isoformat(), "v": 2})
    payload, artifact = acquisition.json_document("votacao.json?" + query, "votings")
    if not isinstance(payload, list):
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    return [normalize_voting(row) for row in payload], artifact


def normalize_voting(row):
    required = ("codigoSessaoVotacao", "dataSessao", "idProcesso", "votacaoSecreta")
    if any(row.get(key) is None for key in required):
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    if row["votacaoSecreta"] not in {"S", "N"}:
        raise IngestionError("SENATE_VOTING_SCHEMA_CHANGED")
    return {
        "source_key": str(row["codigoSessaoVotacao"]),
        "proposition_source_key": str(row["idProcesso"]),
        "occurred_on": date.fromisoformat(row["dataSessao"]).isoformat(),
        "description": row.get("descricaoVotacao"),
        "body": row.get("casaSessao"),
        "collective_result_code": row.get("resultadoVotacao"),
        "final_outcome": None,
        "is_secret": row["votacaoSecreta"] == "S",
        "nominal_vote_evidence": [] if row["votacaoSecreta"] == "S" else row.get("votos", []),
        "totals": {
            key: row.get(key)
            for key in (
                "totalVotosSim",
                "totalVotosNao",
                "totalVotosAbstencao",
            )
        },
    }
