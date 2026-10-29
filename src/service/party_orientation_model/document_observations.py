"""Intermediate literal observations; deliberately incompatible with scoring evidence."""

import hashlib
import re

OBSERVATION_SCHEMA = "party_document_observations.v1"
TOPIC_PATTERNS = {
    "economy_state": r"econom|propriedade|privatiza|mercado|tribut|imposto|estata",
    "social_rights": r"socia[li]|trabalh|saúde|educa|desigual|pobreza|salário",
    "democratic_rules": r"democr|liberdade|direitos|censura|plural|minoria",
    "environment": r"ambiente|ambiental|sustent|clima",
    "declared_identity": r"socialis|comunis|trabalhismo|centro.direita|centro.esquerda",
}
COMPILED_TOPICS = {
    name: re.compile(pattern, re.IGNORECASE) for name, pattern in TOPIC_PATTERNS.items()
}


def normalized_excerpt(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def observation_identifier(political_party: str, source_hash: str, locator: str, excerpt: str):
    payload = "\0".join((political_party.casefold(), source_hash, locator, excerpt))
    return hashlib.sha256(payload.encode()).hexdigest()


def literal_observation(source: dict, excerpt: str, locator: dict, topics: list[str]) -> dict:
    excerpt = normalized_excerpt(excerpt)
    identifier = observation_identifier(
        source["political_party"], source["sha256"], str(sorted(locator.items())), excerpt
    )
    return {
        "observation_id": identifier,
        "political_party": source["political_party"],
        "political_party_identity": source.get("political_party_identity"),
        "source": source,
        "locator": locator,
        "literal_excerpt": excerpt,
        "observation_kind": "document_text_candidate",
        "themes": sorted(set(topics)),
        "fact_unit_id": None,
        "factual_summary": None,
        "attribution": "unreviewed_document_text",
        "action_status": "not_established",
        "validity_start": None,
        "validity_end": None,
        "stance": None,
        "review_status": "pending_context_review",
        "scoring_eligible": False,
        "uncertainties": [
            "date_of_access_is_not_validity",
            "text_match_is_not_action",
            "institutional_authorship_and_context_require_review",
        ],
    }


def candidate_observations(source: dict, pages: list[str]) -> list[dict]:
    """One candidate per distinct paragraph, with all matching topics on the same record."""
    observations, seen = [], set()
    for page_index, page in enumerate(pages):
        for block_index, block in enumerate(re.split(r"\n\s*\n", page)):
            paragraph = normalized_excerpt(block)
            themes = [
                name for name, pattern in COMPILED_TOPICS.items() if pattern.search(paragraph)
            ]
            if not themes or len(paragraph) < 40 or paragraph in seen:
                continue
            seen.add(paragraph)
            excerpt = paragraph[:240]
            locator = {
                "page": page_index + 1,
                "block": block_index + 1,
                "format": source["format"],
                "excerpt_truncated": len(paragraph) > 240,
            }
            observations.append(literal_observation(source, excerpt, locator, themes))
    return observations


def reviewed_observation(
    source: dict,
    excerpt: str,
    locator: dict,
    summary: str,
    attribution: str,
    themes: list[str],
    *,
    visual=False,
) -> dict:
    """A reviewed source assertion remains discourse, never proof of implemented behavior."""
    record = literal_observation(source, excerpt, locator, themes)
    fact_payload = "\0".join((source["political_party"], summary, attribution))
    record.update(
        {
            "fact_unit_id": hashlib.sha256(fact_payload.encode()).hexdigest(),
            "factual_summary": summary,
            "attribution": attribution,
            "observation_kind": "reviewed_source_assertion",
            "review_status": "context_reviewed",
            "review_method": "visual_pdf_review" if visual else "archived_text_context_review",
            "action_status": "declared_position_not_implementation",
            "uncertainties": [
                "statement_does_not_prove_behavior",
                "validity_interval_unestablished",
                "ideological_stance_not_assigned",
            ],
        }
    )
    return record


def verify_source_bytes(content: bytes, expected_sha256: str) -> None:
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("ARCHIVED_DOCUMENT_HASH_MISMATCH")
