"""Reversible JSON form of the raw profile reads. Pure: no network, no database.

Every dict is written as an ordered list of pairs (jsonb itself does not keep key order, and the
live path exposes some rows verbatim); dates, datetimes, Decimals, UUIDs and tuples are tagged
so that `decode_reads(encode_reads(x)) == x` with the exact Python types. Anything else raises
TypeError so that an unforeseen value skips that person instead of corrupting the snapshot.
"""

import json
import math
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

FORMAT_VERSION = 1
TAG = "__t"
_SCALARS = (str, int, bool, type(None))


_TAGGED = (
    (datetime, "datetime", datetime.isoformat),  # before date: datetime is a date subclass
    (date, "date", date.isoformat),
    (Decimal, "decimal", str),
    (UUID, "uuid", str),
)


def _plain(value):
    if isinstance(value, _SCALARS):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("non-finite float")
        return value
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("non-string dict key")
        return {TAG: "dict", "items": [[key, _plain(item)] for key, item in value.items()]}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return {TAG: "tuple", "items": [_plain(item) for item in value]}
    for kind, name, render in _TAGGED:
        if isinstance(value, kind):
            return {TAG: name, "value": render(value)}
    raise TypeError(f"unsupported type {type(value).__name__}")


def _restore(value):
    if isinstance(value, list):
        return [_restore(item) for item in value]
    if not isinstance(value, dict):
        return value
    kind = value[TAG]
    if kind == "dict":
        return {key: _restore(item) for key, item in value["items"]}
    if kind == "tuple":
        return tuple(_restore(item) for item in value["items"])
    parsers = {
        "datetime": datetime.fromisoformat,
        "date": date.fromisoformat,
        "decimal": Decimal,
        "uuid": UUID,
    }
    return parsers[kind](value["value"])


def encode_reads(reads: dict) -> str:
    """Deterministic text: identical reads always give identical bytes (stable version hash)."""
    envelope = {"format": FORMAT_VERSION, "reads": _plain(reads)}
    text = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    if "\x00" in text or "\\u0000" in text:
        raise ValueError("NUL character cannot be stored in jsonb")
    return text


def decode_reads(document) -> dict:
    """Accept the text or the parsed jsonb; a foreign format version is an error (fallback)."""
    parsed = json.loads(document) if isinstance(document, (str, bytes)) else document
    if not isinstance(parsed, dict) or parsed.get("format") != FORMAT_VERSION:
        raise ValueError("PERSON_PROFILE_SNAPSHOT_FORMAT")
    return _restore(parsed["reads"])
