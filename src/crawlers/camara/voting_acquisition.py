"""Period-wide discovery and deduplicated event/subject requests, never per candidate."""

import json
from datetime import date
from urllib.parse import urlencode

from crawlers.camara.voting_normalization import (
    normalize_voting_event,
    related_matter_uri,
    voting_identifier,
)
from service.ingestion.contracts import IngestionError
from storage.files import hash_content


def discover_votings(acquisition, start, end, maximum):
    query = urlencode(
        {
            "dataInicio": start.isoformat(),
            "dataFim": end.isoformat(),
            "itens": 100,
            "ordem": "ASC",
            "ordenarPor": "dataHoraRegistro",
        }
    )
    selected, seen, artifacts = [], {}, []
    for rows, artifact in acquisition.pages("votacoes?" + query, "camara_voting_discovery"):
        artifacts.append(artifact)
        if select_discovery_page(rows, selected, seen, start, end, maximum):
            return selected, artifacts, False
        document = json.loads(artifact.path.read_bytes())
        has_next = any(link.get("rel") == "next" for link in document.get("links", []))
        if len(selected) >= maximum and has_next:
            return selected, artifacts, False
    return selected, artifacts, True


def validate_discovered_voting(row, start, end):
    key = voting_identifier(row)
    try:
        occurred_on = date.fromisoformat(row["data"])
    except (KeyError, TypeError, ValueError) as error:
        raise IngestionError("CAMARA_VOTING_DATE_CHANGED") from error
    if not start <= occurred_on <= end:
        raise IngestionError("CAMARA_VOTING_OUTSIDE_PARTITION")
    return key


def select_discovery_page(rows, selected, seen, start, end, maximum):
    for row in rows:
        key = validate_discovered_voting(row, start, end)
        digest = hash_content(row)
        if key in seen:
            if seen[key] != digest:
                raise IngestionError("CAMARA_VOTING_SNAPSHOT_CONFLICT")
            continue
        if len(selected) >= maximum:
            return True
        seen[key] = digest
        selected.append(row)
    return False


def collect_voting_documents(acquisition, selected, maximum_votes):
    collected, total = [], 0
    for discovery in selected:
        key = voting_identifier(discovery)
        document, detail_artifact = acquisition.json_document(
            "votacoes/" + key, "camara_voting_detail"
        )
        if not isinstance(document.get("dados"), dict):
            raise IngestionError("CAMARA_VOTING_DETAIL_SCHEMA_CHANGED")
        normalize_voting_event(discovery, document["dados"])
        votes, artifacts = [], [detail_artifact]
        for rows, artifact in acquisition.pages(
            "votacoes/" + key + "/votos", "camara_person_votes"
        ):
            total += len(rows)
            if total > maximum_votes:
                raise IngestionError("CAMARA_PERSON_VOTE_BUDGET_EXCEEDED")
            votes.extend(rows)
            artifacts.append(artifact)
        collected.append(
            {
                "discovery": discovery,
                "detail": document["dados"],
                "votes": votes,
                "artifacts": artifacts,
            }
        )
    return collected


def collect_identified_matters(acquisition, events, maximum):
    matters, artifacts, deferred = {}, {}, set()
    for event in events:
        uri = related_matter_uri(event)
        if uri is None or uri in matters or uri in deferred:
            continue
        candidates = (event["detail"].get("objetosPossiveis") or []) + (
            event["detail"].get("proposicoesAfetadas") or []
        )
        embedded = [row for row in candidates if row.get("uri") == uri and row.get("ementa")]
        if len(embedded) == 1:
            matters[uri] = embedded[0]
            continue
        if len(artifacts) >= maximum:
            deferred.add(uri)
            continue
        document, artifact = acquisition.json_document(uri, "camara_voting_proposition")
        matter = document.get("dados")
        if not isinstance(matter, dict) or matter.get("uri") != uri:
            raise IngestionError("CAMARA_VOTING_PROPOSITION_SCHEMA_CHANGED")
        matters[uri], artifacts[uri] = matter, artifact
    return matters, artifacts, len(deferred)
