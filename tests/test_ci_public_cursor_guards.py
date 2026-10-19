"""Public cursors bind filters and reject forged JSON types with stable errors."""

import base64
import json
from dataclasses import replace
from datetime import date, datetime

import pytest

from service.public_profile.contracts import PublicProfileError, VoteQuery
from service.public_profile.pagination import decode_vote_cursor, filter_fingerprint
from service.public_profile.people_contracts import (
    PeopleQuery,
    decode_people_cursor,
    search_fingerprint,
    validate_as_of,
    validate_person_id,
)

PERSON = "00000000-0000-0000-0000-000000000001"
AS_OF = date(2024, 1, 1)


def encoded(payload):
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "fields",
    [
        {"start_on": datetime(2024, 1, 1)},
        {"end_on": date(2023, 1, 1)},
        {"limit": True},
        {"office_kind": []},
        {"exercise_id": True},
        {"exercise_id": 2**63},
        {"person_id": None},
    ],
)
def test_vote_query_rejects_noncanonical_types_and_out_of_range_identifiers(fields):
    with pytest.raises(PublicProfileError):
        VoteQuery(**({"person_id": PERSON, "start_on": AS_OF, "end_on": AS_OF} | fields))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p | {"extra": "field"},
        lambda p: p | {"v": 2},
        lambda p: p | {"filters": "another profile"},
        lambda p: p | {"id": True},
        lambda p: p | {"id": 2**63},
        lambda p: p | {"date": "2023-12-31"},
        lambda p: p | {"date": "invalid"},
        lambda _: [],
    ],
)
def test_vote_cursor_rejects_structurally_valid_but_forged_payloads(mutate):
    query = VoteQuery(PERSON, AS_OF, AS_OF)
    payload = {"v": 1, "filters": filter_fingerprint(query), "date": "2024-01-01", "id": 1}
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_vote_cursor(replace(query, cursor=encoded(mutate(payload))))


@pytest.mark.parametrize(
    "payload", [None, {}, [1], [2, "fingerprint", "Name", PERSON], [1, "fingerprint", 2, PERSON]]
)
def test_people_cursor_rejects_invalid_json_shapes_and_versions(payload):
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_people_cursor(PeopleQuery(cursor=encoded(payload)), AS_OF)


@pytest.mark.parametrize("name", [2, "N" * 501])
def test_people_cursor_requires_bounded_display_name(name):
    query = PeopleQuery()
    payload = [1, search_fingerprint(query, AS_OF), name, PERSON]
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_people_cursor(replace(query, cursor=encoded(payload)), AS_OF)


@pytest.mark.parametrize("value", [None, 1, "bad"])
def test_public_person_identifier_errors_never_expose_internal_uuid_exception(value):
    with pytest.raises(PublicProfileError, match="INVALID_PERSON_ID"):
        validate_person_id(value)


def test_reference_day_rejects_datetime_instead_of_silently_changing_scope():
    with pytest.raises(PublicProfileError, match="INVALID_REFERENCE_DATE"):
        validate_as_of(datetime(2024, 1, 1))
