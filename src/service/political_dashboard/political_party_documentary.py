"""Read reviewed documentary evidence without changing expert classifications."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _documentary_catalog() -> dict:
    catalog_path = Path(__file__).with_name("political_party_documentary_catalog.json")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def get_political_party_documentary_profile(political_party: str) -> dict | None:
    """Return reviewed documentary records, never an inferred historical score.

    Explicit aliases identify records only. Source dates and limitations remain
    attached to every result; absence does not imply any ideological position.
    """
    requested_label = political_party.strip().casefold()
    for record in _documentary_catalog()["records"]:
        labels = [record["political_party"], *record.get("aliases", [])]
        if requested_label in {label.casefold() for label in labels}:
            return deepcopy(record)
    return None


def get_political_party_documentary_catalog() -> dict:
    """Return compact sources, methodological limits and all reviewed records."""
    return deepcopy(_documentary_catalog())
