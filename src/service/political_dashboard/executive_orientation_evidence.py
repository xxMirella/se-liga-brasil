"""Dated academic evidence about governments, independent of party surveys."""

import json
from copy import deepcopy
from datetime import date
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _executive_evidence() -> dict:
    path = Path(__file__).with_suffix(".json")
    return json.loads(path.read_text(encoding="utf-8"))


def classify_executive_orientation(executive_source_id: str, year: int) -> dict:
    """Match explicit executive identity and studied years, never party labels."""
    for record in _executive_evidence()["records"]:
        if executive_source_id in {record["executive_source_id"], record["exercise_id"]}:
            if year not in record["valid_years"]:
                continue
            result = deepcopy(record)
            if record.get("period_start"):
                result["coverage_start"] = max(
                    date(year, 1, 1), date.fromisoformat(record["period_start"])
                ).isoformat()
                result["coverage_end_exclusive"] = min(
                    date(year + 1, 1, 1), date.fromisoformat(record["period_end_exclusive"])
                ).isoformat()
            return result
    return {
        "category": "undetermined",
        "label": "Sem classificação de governo",
        "status": "no_documented_government_analysis",
        "executive_source_id": executive_source_id,
        "reference_year": year,
    }


def get_executive_orientation_evidence_catalog() -> dict:
    """Return provenance and research scope for reviewed government evidence."""
    return deepcopy(_executive_evidence())


def classify_regime_orientation(regime_source_id: str, year: int) -> dict:
    """Return regime evidence clipped to the actual portion of a calendar year."""
    for record in _executive_evidence().get("regime_records", []):
        if record["regime_source_id"] != regime_source_id:
            continue
        start = max(date(year, 1, 1), date.fromisoformat(record["period_start"]))
        end = min(date(year + 1, 1, 1), date.fromisoformat(record["period_end_exclusive"]))
        if start >= end:
            continue
        result = deepcopy(record)
        result["coverage_start"] = start.isoformat()
        result["coverage_end_exclusive"] = end.isoformat()
        complete = start == date(year, 1, 1) and end == date(year + 1, 1, 1)
        result["year_coverage"] = "full" if complete else "partial"
        return result
    return {"category": "undetermined", "status": "no_documented_regime_analysis"}
