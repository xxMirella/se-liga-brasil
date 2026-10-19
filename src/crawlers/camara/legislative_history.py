"""Opt-in, bounded acquisition of shared proposition history without personal IDs."""

from urllib.parse import urlparse

from crawlers.camara.configuration import API_BASE
from crawlers.camara.legislative_normalization import (
    normalize_author,
    normalize_collective_decision,
    normalize_legislative_detail,
    normalize_proceeding,
)
from crawlers.camara.pipeline import ingest_collected
from service.ingestion.contracts import IngestionError


def proposition_identifier(official_key):
    parsed = urlparse(official_key)
    prefix = urlparse(API_BASE + "proposicoes/")
    identifier = parsed.path.removeprefix(prefix.path)
    if (
        parsed.scheme != "https"
        or parsed.netloc != prefix.netloc
        or not parsed.path.startswith(prefix.path)
        or not identifier.isdecimal()
        or parsed.query
        or parsed.fragment
    ):
        raise IngestionError("CAMARA_INVALID_PROPOSITION_KEY")
    return identifier


def collect_legislative_history(
    acquisition, repository, proposition_keys, *, resolve_person=None, max_propositions=25
):
    if max_propositions < 1:
        raise ValueError("max_propositions must be positive")
    seen, results = set(), []
    for official_key in proposition_keys:
        identifier = proposition_identifier(official_key)
        if identifier in seen:
            continue
        if len(seen) >= max_propositions:
            raise IngestionError("CAMARA_PROPOSITION_BUDGET_EXCEEDED")
        seen.add(identifier)
        results.append(
            collect_proposition_history(acquisition, repository, identifier, resolve_person)
        )
    return results


def collect_proposition_history(acquisition, repository, identifier, resolve_person):
    path = f"proposicoes/{identifier}"
    document, artifact = acquisition.json_document(path, "camara_legislative_detail")
    detail = normalize_legislative_detail(document["dados"])
    expected_key = API_BASE + path
    if detail["officialKey"] != expected_key:
        raise IngestionError("CAMARA_PROPOSITION_IDENTITY_MISMATCH")
    ingest_collected(repository, acquisition, artifact, [detail])
    result = {"official_key": expected_key, "detail": True}
    for endpoint in ("tramitacoes", "autores", "relacionadas", "votacoes"):
        count = 0
        kind = "camara_legislative_" + endpoint
        for rows, artifact in acquisition.pages(path + "/" + endpoint, kind):
            normalized = normalize_history_page(rows, endpoint, expected_key, resolve_person)
            ingest_collected(repository, acquisition, artifact, normalized)
            count += len(normalized)
        result[endpoint] = count
    result["coverage"] = "requested_endpoints_complete_not_entire_public_career"
    return result


def normalize_history_page(rows, endpoint, official_key, resolve_person):
    normalized, seen = [], set()
    for row in rows:
        fact = normalize_history_row(row, endpoint, official_key, resolve_person)
        if fact is not None and fact["recordKey"] not in seen:
            seen.add(fact["recordKey"])
            normalized.append(fact)
    return normalized


def normalize_history_row(row, endpoint, official_key, resolve_person):
    if endpoint == "tramitacoes":
        return normalize_proceeding(row, official_key)
    if endpoint == "autores":
        return normalize_author(row, official_key, resolve_person) if resolve_person else None
    if endpoint == "votacoes":
        return normalize_collective_decision(row, official_key)
    if not row.get("uri"):
        raise IngestionError("CAMARA_RELATED_PROPOSITION_SCHEMA_CHANGED")
    return {
        "officialKey": official_key,
        "recordKey": official_key + ":related:" + row["uri"],
        "relatedProposition": row["uri"],
        "relation": "official_related_not_inferred_legal_conversion",
        "kind": row.get("siglaTipo"),
    }
