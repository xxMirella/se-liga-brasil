"""Collects stored extractions of one party into a single pending-review evidence file."""

import json
from pathlib import Path

from service.party_discourse_extraction.evidence_conversion import convert_record
from service.party_discourse_extraction.rubric_indicators import RubricIndicator

PENDING_EVIDENCE_FILE = "evidence_pending_review.json"


def export_pending_evidence(
    extractions_root: Path, political_party: str, indicators_by_code: dict[str, RubricIndicator]
) -> Path:
    directory = extractions_root / political_party
    evidence: list[dict] = []
    for path in sorted(directory.glob("*__*.json")):
        if path.name == PENDING_EVIDENCE_FILE:
            continue
        evidence.extend(convert_record(json.loads(path.read_text()), indicators_by_code))
    target = directory / PENDING_EVIDENCE_FILE
    batch = {
        "schema": "party_orientation_evidence_batch.v1",
        "review_status": "pending_human_review",
        "evidence": evidence,
    }
    target.write_text(json.dumps(batch, ensure_ascii=False, indent=1))
    return target
