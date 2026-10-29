"""Converts accepted items into party_orientation_evidence.v1 candidates for the discourse layer.

Candidates carry weight 0 and `pending_human_review`: the model never reads them until a person
confirms each item. Evidence about indicators with contested direction is display only.
"""

import hashlib

from service.party_discourse_extraction.rubric_indicators import RubricIndicator

EVIDENCE_SCHEMA = "party_orientation_evidence.v1"
STRENGTH_SCALE = 3


def candidate_evidence(record: dict, passage: dict, item: dict, indicator: RubricIndicator):
    """None for items that state no direction ("nao_se_aplica"): there is nothing to score."""
    if item["direction"] is None:
        return None
    document = record["document"]
    year = int((document["document_date"] or document["retrieved_on"])[:4])
    quote_suffix = passage["segment_id"].rsplit("-", 1)[-1]
    return {
        "schema": EVIDENCE_SCHEMA,
        "evidence_id": f"discourse:{record['political_party'].lower()}:"
        f"{record['provenance']['model']}:{document['sha256'][:12]}:{quote_suffix}:"
        f"{indicator.code}:{_item_hash(item)}",
        "political_party": record["political_party"],
        "layer": "discourse",
        "indicator_id": indicator.indicator_id,
        "dimension": indicator.dimension,
        "stance": round(item["direction"] * item["strength"] / STRENGTH_SCALE, 3),
        "attribution_basis": "party_official_document",
        "proof_level": "documented_primary",
        "source_id": f"party-document-{document['sha256'][:12]}",
        "source_url": document["source_url"],
        "source_date": document["document_date"] or document["retrieved_on"],
        "document_date_known": document["document_date"] is not None,
        "year_start": year,
        "year_end": year,
        "description": _description(record, passage, item),
        "human_reviewed": False,
        "review_status": "pending_human_review",
        "weight_override": 0.0,
        "display_only": indicator.contested_direction,
        "extraction_consistency": item["consistency"],
    }


def _item_hash(item: dict) -> str:
    return hashlib.sha256(item["quote"].encode()).hexdigest()[:8]


def _description(record: dict, passage: dict, item: dict) -> str:
    provenance = record["provenance"]
    return (
        f"Citação do trecho (partido oculto na leitura): «{item['quote']}». "
        f"Tipo: {item['commitment_type']}; força {item['strength']}/3. "
        f"Leitura automatizada ({provenance['model']}, {provenance['prompt_version']}), "
        f"origem do texto: {passage['text_origin']}; consistência entre execuções: "
        f"{item['consistency']}. Sem revisão humana."
    )


def convert_record(record: dict, indicators_by_code: dict[str, RubricIndicator]) -> list[dict]:
    evidence = []
    for passage in record["passages"]:
        for item in passage["items"]:
            indicator = indicators_by_code[item["indicator"]]
            candidate = candidate_evidence(record, passage, item, indicator)
            if candidate is not None:
                evidence.append(candidate)
    return evidence
