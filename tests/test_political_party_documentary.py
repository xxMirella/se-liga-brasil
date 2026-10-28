"""Prevent documentary evidence from becoming unsupported ideological labels."""
import json
import re

from service.political_dashboard.political_party_documentary import (
    get_political_party_documentary_catalog,
    get_political_party_documentary_profile,
)


def test_complete_review_has_compact_traceable_sources():
    catalog = get_political_party_documentary_catalog()
    assert len(catalog["records"]) == 22
    assert len({record["political_party"] for record in catalog["records"]}) == 22
    encoded = json.dumps(catalog)
    assert "original_body_gzip_base64" not in encoded
    assert "review_text" not in encoded
    for record in catalog["records"]:
        assert record["positions"]
        assert len((record["self_description"].get("literal_quote") or "").split()) <= 25
        for source_id in record["source_ids"]:
            source = catalog["sources"][source_id]
            assert source["source_url"].startswith("https://")
            assert re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
            assert source["hash_scope"]


def test_dimensional_and_doctrinal_terms_are_not_global_spatial_labels():
    for label in ("MDB", "MISSÃO", "REDE", "REPUBLICANOS"):
        record = get_political_party_documentary_profile(label)
        assert record["self_description"].get("global_label") is None
    mission = get_political_party_documentary_profile("MISSÃO")
    assert "candidate_campaign" not in mission["source_ids"]


def test_unaffiliated_and_historical_identity_do_not_gain_current_program():
    assert get_political_party_documentary_profile("S/Partido") is None
    assert get_political_party_documentary_profile("PSD (1945)") is None
    assert get_political_party_documentary_profile("not a political party") is None


def test_callers_cannot_mutate_cached_documentary_evidence():
    record = get_political_party_documentary_profile("PT")
    record["limitations"].append("mutation")
    assert "mutation" not in get_political_party_documentary_profile("PT")["limitations"]
    catalog = get_political_party_documentary_catalog()
    catalog["sources"].clear()
    assert get_political_party_documentary_catalog()["sources"]
