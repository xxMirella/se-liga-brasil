"""History cursors pin published catalog and exercise context, without loading every Parquet."""

import base64
import hashlib
import json
import re
from datetime import date

from service.analytical_datasets.contracts import validate_voting_key
from service.public_profile.contracts import PublicProfileError
from service.public_profile.pagination import filter_fingerprint


def history_fingerprint(query):
    return hashlib.sha256(("history:" + filter_fingerprint(query)).encode()).hexdigest()


def create_history_snapshot(reader, query, partitions, exercise_context):
    reader.prune_expired_cache()
    payload = {
        "created_at": reader.clock(),
        "filters": history_fingerprint(query),
        "catalog": partitions,
        "exercise_context": exercise_context,
        "entries": [],
    }
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    token = hashlib.sha256(content).hexdigest()
    reader.save_bytes(reader.directory / (token + ".snapshot.json"), content)
    return token, payload


def encode_history_cursor(token, fingerprint, position, row=None):
    payload = {
        "v": 3,
        "snapshot": token,
        "filters": fingerprint,
        "position": position,
        "date": row["occurred_on"] if row else None,
        "id": row["voting_id"] if row else None,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode_history_cursor(query):
    if query.cursor is None:
        return None
    try:
        if not isinstance(query.cursor, str) or len(query.cursor) > 1024:
            raise ValueError("Invalid cursor")
        payload = json.loads(
            base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
            )
        )
        if set(payload) != {"v", "snapshot", "filters", "position", "date", "id"}:
            raise ValueError("Invalid fields")
        if payload["v"] != 3 or payload["filters"] != history_fingerprint(query):
            raise ValueError("Invalid filters")
        if not re.fullmatch(r"[a-f0-9]{64}", payload["snapshot"]):
            raise ValueError("Invalid snapshot")
        if type(payload["position"]) is not int or not 0 <= payload["position"] <= 100000:
            raise ValueError("Invalid position")
        validate_history_event_cursor(payload, query)
        return payload
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise PublicProfileError("INVALID_CURSOR") from error


def validate_history_event_cursor(payload, query):
    if (payload["date"] is None) != (payload["id"] is None):
        raise ValueError("Incomplete event")
    if payload["date"] is not None:
        if not query.start_on <= date.fromisoformat(payload["date"]) <= query.end_on:
            raise ValueError("Invalid day")
        validate_voting_key(payload["id"], allow_event_keys=True)
