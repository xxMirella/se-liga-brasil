"""Validated public person search and filter-bound keyset pagination."""

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from service.public_profile.contracts import OFFICE_KINDS, PublicProfileError

UFS = frozenset(
    [
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PE",
        "PI",
        "PR",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    ]
)


@dataclass(frozen=True)
class PeopleQuery:
    q: str = ""
    uf: str | None = None
    office_kind: str | None = None
    political_party: str | None = None
    cursor: str | None = None
    limit: int = 30

    def __post_init__(self):
        if not isinstance(self.q, str) or len(self.q) > 120:
            raise PublicProfileError("INVALID_SEARCH")
        object.__setattr__(self, "q", " ".join(self.q.split()))
        if self.q and len(self.q) < 2:
            raise PublicProfileError("INVALID_SEARCH")
        if self.uf is not None and self.uf not in UFS:
            raise PublicProfileError("INVALID_UF")
        if self.office_kind is not None and self.office_kind not in OFFICE_KINDS:
            raise PublicProfileError("INVALID_OFFICE_KIND")
        if self.political_party is not None and not re.fullmatch(
            r"[A-Za-z0-9 .-]{1,40}", self.political_party
        ):
            raise PublicProfileError("INVALID_POLITICAL_PARTY")
        if type(self.limit) is not int or not 1 <= self.limit <= 100:
            raise PublicProfileError("INVALID_PAGE_SIZE")


def validate_person_id(person_id):
    try:
        return str(UUID(person_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise PublicProfileError("INVALID_PERSON_ID") from error


def search_fingerprint(query, as_of):
    fields = [query.q, query.uf, query.office_kind, query.political_party, str(as_of)]
    return hashlib.sha256(json.dumps(fields).encode()).hexdigest()


def encode_people_cursor(query, as_of, row):
    payload = [1, search_fingerprint(query, as_of), row["display_name"], row["person_id"]]
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode_people_cursor(query, as_of):
    if query.cursor is None:
        return None
    try:
        if not isinstance(query.cursor, str) or len(query.cursor) > 2048:
            raise ValueError("Invalid cursor")
        payload = json.loads(
            base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
            )
        )
        if not isinstance(payload, list) or len(payload) != 4:
            raise ValueError("Invalid payload")
        if payload[0] != 1 or payload[1] != search_fingerprint(query, as_of):
            raise ValueError("Invalid filters")
        if not isinstance(payload[2], str) or len(payload[2]) > 500:
            raise ValueError("Invalid name")
        return payload[2], validate_person_id(payload[3])
    except (ValueError, TypeError, AttributeError) as error:
        raise PublicProfileError("INVALID_CURSOR") from error


def validate_as_of(as_of):
    if type(as_of) is not date:
        raise PublicProfileError("INVALID_REFERENCE_DATE")
