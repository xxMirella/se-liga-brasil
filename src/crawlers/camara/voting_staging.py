"""Build strict private analytical inputs from verified identities and published facts."""

from crawlers.camara.voting_identity import voter_profile_key
from crawlers.camara.voting_normalization import (
    identified_matter_uri,
    matter_fields,
    normalize_individual_vote,
    normalize_voting_event,
    related_matter_uri,
)
from service.ingestion.contracts import IngestionError
from service.voting_pipeline.source_storage import latest_source_observation
from storage.files import hash_content

PARSER_VERSION = "camara-daily-voting-input-v6"


def latest_artifact_observation(artifacts):
    return latest_source_observation(*(artifact.fetched_at for artifact in artifacts))


def deduplicate_individual_votes(votes):
    seen, result = {}, []
    for vote in votes:
        key = voter_profile_key(vote)
        if key is None:
            result.append(vote)
            continue
        digest = hash_content(vote)
        if key in seen:
            if seen[key] != digest:
                raise IngestionError("CAMARA_INDIVIDUAL_VOTE_SNAPSHOT_CONFLICT")
            continue
        seen[key] = digest
        result.append(vote)
    return result


def build_daily_records(events, identities, matters, matter_artifacts):
    rows, unresolved, descriptions_missing = [], 0, 0
    for event in events:
        normalized = normalize_voting_event(event["discovery"], event["detail"])
        uri = related_matter_uri(event)
        matter = event_matter_fields(event, normalized, matters, uri)
        event_artifacts = list(event["artifacts"])
        if uri in matter_artifacts:
            event_artifacts.append(matter_artifacts[uri])
        event_hash = hash_content(sorted({artifact.sha256 for artifact in event_artifacts}))
        event_observed_at = latest_artifact_observation(event_artifacts)
        seen_people = set()
        for vote in deduplicate_individual_votes(event["votes"]):
            identity = identities.get(voter_profile_key(vote))
            if identity is None:
                unresolved += 1
                continue
            person_id = identity["person_id"]
            if person_id in seen_people:
                raise IngestionError("CAMARA_DUPLICATE_CANONICAL_VOTER")
            seen_people.add(person_id)
            evidence_hash = hash_content([event_hash, identity["artifact"].sha256])
            record = (
                normalized
                | matter
                | normalize_individual_vote(vote)
                | {
                    "person_id": person_id,
                    "evidence_sha256": evidence_hash,
                    "validation_status": "verified",
                    "source_observed_at": latest_source_observation(
                        event_observed_at, identity["artifact"].fetched_at
                    ),
                }
            )
            rows.append(record)
            descriptions_missing += record["description"] is None
    return rows, unresolved, descriptions_missing


def event_matter_fields(event, normalized, matters, uri):
    source_matter = matters.get(uri) or {}
    matter = matter_fields(matters.get(uri), normalized["official_url"])
    matter.update(matter_document_url=source_matter.get("uri"),
                  matter_text_url=source_matter.get("urlInteiroTeor"))
    if uri and identified_matter_uri(event["discovery"]) is None and matter["matter_name"]:
        matter["matter_name"] += " · matéria relacionada"
    return matter
