"""Partition the current territorial inventory by UF without asserting historical existence."""

from collections import defaultdict


def build_territorial_catalogs(catalog):
    grouped = defaultdict(list)
    for municipality in catalog["municipalities"]:
        if municipality["uf"] == "DF":
            raise ValueError("DISTRICT_HAS_NO_MUNICIPALITIES")
        grouped[municipality["uf"]].append(municipality)
    return [
        {
            "territory_code": state["uf"],
            "year": int(catalog["observed_at"][:4]),
            "institution_code": "territorial_catalog",
            "municipalities": sorted(grouped[state["uf"]], key=lambda row: row["name"]),
            "temporal_scope": catalog["temporal_scope"],
            "observed_at": catalog["observed_at"],
            "evidence": catalog["evidence"],
        }
        for state in catalog["states"]
    ]
