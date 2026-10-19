"""Bounded document-based discovery supplements the official period index."""

from datetime import date

from crawlers.camara.voting_acquisition import discover_votings, validate_discovered_voting
from service.ingestion.contracts import IngestionError


def discover_proposition_votings(acquisition, identifiers, start, end, selected, maximum):
    identifiers = tuple(dict.fromkeys(str(value) for value in identifiers))
    if len(identifiers) > 100 or any(not key.isdecimal() or int(key) < 1 for key in identifiers):
        raise IngestionError("CAMARA_INVALID_PROPOSITION_SCOPE")
    seen = {row["id"] for row in selected}
    artifacts = []
    for identifier in identifiers:
        for rows, artifact in acquisition.pages(
            f"proposicoes/{identifier}/votacoes", "camara_proposition_voting_discovery"
        ):
            artifacts.append(artifact)
            if not select_document_votes(rows, selected, seen, start, end, maximum):
                return artifacts, False
    return artifacts, True


def select_document_votes(rows, selected, seen, start, end, maximum):
    for row in rows:
        if not start <= date.fromisoformat(row["data"]) <= end:
            continue
        key = validate_discovered_voting(row, start, end)
        if key in seen:
            continue
        if len(selected) >= maximum:
            return False
        seen.add(key)
        selected.append(row)
    return True


def discover_voting_sources(acquisition, start, end, maximum, proposition_ids=()):
    if proposition_ids:
        selected = []
        artifacts, complete = discover_proposition_votings(
            acquisition, proposition_ids, start, end, selected, maximum
        )
        return selected, artifacts, complete
    return discover_votings(acquisition, start, end, maximum)
