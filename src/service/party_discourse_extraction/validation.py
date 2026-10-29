"""Deterministic gate: an item survives only if its quote exists word for word in the passage."""

import json
import re
import unicodedata
from dataclasses import dataclass

from service.party_discourse_extraction.prompt import (
    COMMITMENT_TYPES,
    DIRECTIONS,
    MAX_QUOTE_CHARACTERS,
)

MIN_QUOTE_WORDS = 4
QUOTE_TRANSLATION = str.maketrans(
    {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", " ": " ", "­": ""}
)
PLACEHOLDER_ONLY = re.compile(r"^(\s*\[[A-ZÇÃ]+\]\s*)+$")


@dataclass(frozen=True)
class ExtractedItem:
    indicator_code: str
    direction: int | None  # None means "nao_se_aplica"
    strength: int
    commitment_type: str
    quote: str


@dataclass(frozen=True)
class DiscardedItem:
    reason: str
    raw: dict


def normalize_for_matching(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).translate(QUOTE_TRANSLATION)
    return " ".join(folded.split())


def quote_exists(quote: str, passage: str) -> bool:
    return normalize_for_matching(quote) in normalize_for_matching(passage)


def _valid_strength(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 3


def _rejection_reason(raw: dict, passage: str, valid_codes: set[str]) -> str | None:
    quote = raw.get("quote")
    checks = (
        (raw.get("indicator") not in valid_codes, "indicator_unknown"),
        (raw.get("direction") not in DIRECTIONS, "direction_invalid"),
        (raw.get("commitment_type") not in COMMITMENT_TYPES, "commitment_type_invalid"),
        (not _valid_strength(raw.get("strength")), "strength_invalid"),
        (not isinstance(quote, str) or len(quote.split()) < MIN_QUOTE_WORDS, "quote_too_short"),
    )
    for failed, reason in checks:
        if failed:
            return reason
    if len(quote) > MAX_QUOTE_CHARACTERS or PLACEHOLDER_ONLY.match(quote):
        return "quote_unusable"
    return None if quote_exists(quote, passage) else "quote_not_in_passage"


def _to_item(raw: dict) -> ExtractedItem:
    direction = None if raw["direction"] == "nao_se_aplica" else int(raw["direction"])
    return ExtractedItem(
        raw["indicator"], direction, raw["strength"], raw["commitment_type"], raw["quote"].strip()
    )


def _item_key(raw: dict) -> tuple[str, str]:
    return raw["indicator"], normalize_for_matching(raw["quote"])


def validate_response(response_text: str, passage: str, valid_codes: set[str]):
    """Return (accepted, discarded); malformed JSON discards the whole answer, never guesses."""
    try:
        raw_items = json.loads(response_text)["items"]
    except (ValueError, KeyError, TypeError):
        return [], [DiscardedItem("response_not_valid_json", {})]
    accepted, discarded, seen = [], [], set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            discarded.append(DiscardedItem("item_malformed", {}))
            continue
        reason = _rejection_reason(raw, passage, valid_codes)
        if reason is None and _item_key(raw) in seen:
            reason = "duplicate_item"
        if reason:
            discarded.append(DiscardedItem(reason, raw))
            continue
        seen.add(_item_key(raw))
        accepted.append(_to_item(raw))
    return accepted, discarded
