"""Writes extraction results with provenance; results are evidence candidates, never final."""

import json
from datetime import UTC, datetime
from pathlib import Path

from service.party_discourse_extraction.passage_extraction import PassageResult
from service.party_discourse_extraction.prompt import PROMPT_VERSION


def _item_dict(item) -> dict:
    return {
        "indicator": item.indicator_code,
        "direction": item.direction,
        "strength": item.strength,
        "commitment_type": item.commitment_type,
        "quote": item.quote,
    }


def passage_record(result: PassageResult) -> dict:
    passage = result.passage
    return {
        "segment_id": passage.segment.segment_id,
        "heading": passage.segment.heading,
        "text_origin": passage.text_origin,
        "indicator_hints": list(passage.indicator_hints),
        "masked_counts": passage.masked_counts,
        "blinded_text": passage.blinded_text,
        "original_text": passage.segment.text,
        "items": [
            {**_item_dict(item), "consistency": status} for item, status in result.labeled_items
        ],
        "second_run_items": [_item_dict(item) for item in result.second_run_items],
        "discarded": [
            {"run": run, "reason": item.reason, "raw": item.raw} for run, item in result.discarded
        ],
        "consistency": {
            "agree": result.consistency.agree,
            "direction_conflict": result.consistency.direction_conflict,
            "only_first_run": result.consistency.only_first_run,
            "only_second_run": result.consistency.only_second_run,
            "agreement_rate": result.consistency.agreement_rate,
        },
        "usage": result.usage,
    }


def document_payload(document, model: str, results: list[PassageResult]) -> dict:
    return {
        "schema": "party_discourse_extraction.v1",
        "political_party": document.political_party,
        "document": {
            "sha256": document.sha256,
            "kind": document.kind,
            "source_url": document.source_url,
            "document_date": document.document_date,
            "retrieved_on": document.retrieved_on,
        },
        "provenance": {
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "temperature": 0,
            "runs": 2,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "review_status": "pending_human_review",
        "passages": [passage_record(result) for result in results],
    }


def save_document_extraction(
    root: Path, document, model: str, results: list[PassageResult]
) -> Path:
    path = root / document.political_party / f"{document.short_hash}__{model}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = document_payload(document, model, results)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return path
