"""Filter-bound opaque cursors; clients cannot use them for another profile."""

import base64
import hashlib
import json
from datetime import date

from service.public_profile.contracts import PublicProfileError


def filter_fingerprint(query):
    fields = [
        query.person_id,
        str(query.start_on),
        str(query.end_on),
        query.office_kind,
        query.exercise_id,
    ]
    return hashlib.sha256(json.dumps(fields, separators=(",", ":")).encode()).hexdigest()


def encode_vote_cursor(query, occurred_on, voting_id):
    payload = {
        "v": 1,
        "filters": filter_fingerprint(query),
        "date": occurred_on.isoformat(),
        "id": voting_id,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode_vote_cursor(query):
    if query.cursor is None:
        return None
    try:
        if not isinstance(query.cursor, str) or len(query.cursor) > 512:
            raise ValueError("Invalid cursor length")
        encoded = query.cursor + "=" * (-len(query.cursor) % 4)
        payload = json.loads(base64.b64decode(encoded, altchars=b"-_", validate=True))
        if set(payload) != {"v", "filters", "date", "id"}:
            raise ValueError("Invalid cursor fields")
        occurred_on = date.fromisoformat(payload["date"])
        voting_id = payload["id"]
        if payload["v"] != 1 or payload["filters"] != filter_fingerprint(query):
            raise ValueError("Cursor filters differ")
        if type(voting_id) is not int or not 1 <= voting_id <= 2**63 - 1:
            raise ValueError("Invalid cursor key")
        if not query.start_on <= occurred_on <= query.end_on:
            raise ValueError("Cursor date outside period")
        return occurred_on, voting_id
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise PublicProfileError("INVALID_CURSOR") from error
