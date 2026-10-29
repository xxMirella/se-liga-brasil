"""Intermediate extraction preserves provenance without authorizing ideological scoring."""

import hashlib

import pytest

from service.party_orientation_model.document_observations import (
    candidate_observations,
    reviewed_observation,
    verify_source_bytes,
)


def source(sha256="a" * 64):
    return {"political_party": "FICTITIOUS", "sha256": sha256,
            "format": "html", "url": "https://example.invalid/test"}


def test_multiple_themes_and_duplicate_paragraphs_do_not_multiply_the_observation():
    paragraph = "O documento menciona economia de mercado e direitos sociais e democracia."
    result = candidate_observations(source(), [f"{paragraph}\n\n{paragraph}"])
    assert len(result) == 1
    assert {"economy_state", "social_rights", "democratic_rules"} <= set(result[0]["themes"])
    assert result[0]["stance"] is None
    assert result[0]["action_status"] == "not_established"
    assert result[0]["scoring_eligible"] is False
    assert result[0]["validity_start"] is None


def test_changing_original_changes_observation_identity():
    pages = ["O documento menciona políticas sociais e democracia como temas de interesse."]
    first = candidate_observations(source(), pages)[0]
    second = candidate_observations(source("b" * 64), pages)[0]
    assert first["observation_id"] != second["observation_id"]


def test_same_reviewed_fact_is_not_independent_when_republished():
    arguments = ("defesa da democracia", {"page": 1}, "Declara defender democracia.",
                 "official_party_program", ["democratic_rules"])
    first = reviewed_observation(source(), *arguments)
    second = reviewed_observation(source("b" * 64), *arguments)
    assert first["fact_unit_id"] == second["fact_unit_id"]
    assert first["observation_id"] != second["observation_id"]
    assert first["stance"] is None
    assert first["scoring_eligible"] is False
    assert first["action_status"] == "declared_position_not_implementation"


def test_hash_validation_rejects_tampered_original():
    expected = hashlib.sha256(b"original").hexdigest()
    verify_source_bytes(b"original", expected)
    with pytest.raises(ValueError, match="ARCHIVED_DOCUMENT_HASH_MISMATCH"):
        verify_source_bytes(b"changed", expected)
