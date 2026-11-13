"""Stable JSON form of the `MajorityPanorama` document. Pure: no network, no database.

`encode_document` is deterministic (sorted keys, fixed separators), so identical panoramas always
hash to the same dataset version. `decode_document` rebuilds the exact dataclass structure
(tuples, dates, nested contracts) from the type hints of `contracts`, so a document read from the
serving table is equal to the one the live assembly returns.
"""

import json
import types
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date
from typing import Union, get_args, get_origin, get_type_hints

from service.majority_panorama.contracts import MajorityPanorama

JSON_SEPARATORS = (",", ":")


def _plain(value):
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def encode_document(panorama) -> str:
    return json.dumps(
        _plain(panorama), sort_keys=True, separators=JSON_SEPARATORS, ensure_ascii=False
    )


def _decode(value, hint):
    origin, arguments = get_origin(hint), get_args(hint)
    if origin in {Union, types.UnionType}:
        if value is None:
            return None
        return _decode(value, next(arg for arg in arguments if arg is not type(None)))
    if value is None:
        return None
    if is_dataclass(hint):
        hints = get_type_hints(hint)
        return hint(
            **{
                item.name: _decode(value[item.name], hints[item.name])
                for item in fields(hint)
                if item.name in value
            }
        )
    if hint is date:
        return date.fromisoformat(value)
    if hint in {int, str} and (type(value) is not hint):
        raise ValueError("PANORAMA_DOCUMENT_SCALAR_TYPE")
    if origin is tuple:
        return tuple(_decode(item, arguments[0]) for item in value)
    if origin is not None and issubclass(origin, Mapping):
        return {key: _decode(item, arguments[1]) for key, item in value.items()}
    return value


def decode_document(document) -> MajorityPanorama:
    """Accept the serialized text or the already parsed object (jsonb comes back parsed)."""
    parsed = json.loads(document) if isinstance(document, (str, bytes)) else document
    return _decode(parsed, MajorityPanorama)


def decode_exact(document) -> MajorityPanorama:
    """Decode and prove nothing was dropped, defaulted or mistyped: re-encoding gives the input.

    A document from an older contract (missing or extra fields) or a corrupted one raises
    `ValueError`, so the caller falls back to the live assembly instead of serving a lookalike.
    """
    parsed = json.loads(document) if isinstance(document, (str, bytes)) else document
    try:
        panorama = _decode(parsed, MajorityPanorama)
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError("PANORAMA_DOCUMENT_SHAPE") from error
    if json.loads(encode_document(panorama)) != parsed:
        raise ValueError("PANORAMA_DOCUMENT_NOT_EXACT")
    return panorama
