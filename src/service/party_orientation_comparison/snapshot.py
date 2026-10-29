"""Load and validate the bundled comparison snapshot; production has no data/ directory."""

import json
from functools import lru_cache
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).with_name("snapshot.json")
SCHEMA_VERSION = "party_orientation_comparison_snapshot.v1"
REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "generated_on",
        "catalog_version",
        "model_version",
        "rubric_version",
        "periods",
        "political_parties",
    }
)


def validate_snapshot(snapshot):
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("PARTY_ORIENTATION_COMPARISON_SCHEMA_NOT_SUPPORTED")
    if REQUIRED_KEYS - set(snapshot):
        raise ValueError("PARTY_ORIENTATION_COMPARISON_SNAPSHOT_INCOMPLETE")
    period_ids = {period["period_id"] for period in snapshot["periods"]}
    for entry in snapshot["political_parties"]:
        unknown = {row["period_id"] for row in entry["rows"]} - period_ids
        if unknown:
            raise ValueError("PARTY_ORIENTATION_COMPARISON_PERIOD_UNKNOWN")
    return snapshot


@lru_cache(maxsize=1)
def load_snapshot():
    return validate_snapshot(json.loads(SNAPSHOT_PATH.read_text()))
