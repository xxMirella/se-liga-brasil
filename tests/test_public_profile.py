"""Public read contracts with isolated repositories; never seed production."""

from contextlib import nullcontext
from datetime import date
from uuid import uuid4

import pytest

from service.public_profile import PublicProfileError, VoteQuery, get_person_votes
from service.public_profile.pagination import decode_vote_cursor, encode_vote_cursor

PERSON_ID = str(uuid4())


def voting(voting_id=42, choice="yes", participation="voted"):
    return {
        "voting_id": voting_id,
        "held_on": date(2026, 10, 14),
        "held_at": None,
        "date_precision": "day",
        "subject": "Texto demonstrativo",
        "subject_kind": "main_text",
        "method": "roll_call",
        "collective_result": "approved",
        "stage": "plenary",
        "round_number": 1,
        "legislative_body_code": "plenary",
        "nominal_availability": "available",
        "choice": choice,
        "participation_status": participation,
        "institution_code": "senado",
        "institution_name": "Instituição demonstrativa",
        "proposition_id": 12,
        "proposition_kind": "PL",
        "proposition_number": "1",
        "proposition_year": 2026,
        "proposition_title": "Proposição demonstrativa",
        "source_record_id": 999,
        "private_document": "must never appear",
    }


class Repository:
    def __init__(self, votes=(), person=True, exercises=(), receipts=()):
        self.votes, self.person, self.exercises, self.receipts = votes, person, exercises, receipts
        self.calls = []

    def read_snapshot(self):
        self.calls.append("snapshot")
        return nullcontext()

    def fetch_person(self, person_id):
        self.calls.append("person")
        return (
            {"person_id": person_id, "display_name": "Perfil demonstrativo"}
            if self.person
            else None
        )

    def fetch_exercises(self, query):
        self.calls.append("exercises")
        return self.exercises

    def fetch_votes(self, query, cursor):
        self.calls.append("votes")
        return self.votes

    def fetch_vote_coverage(self, query):
        self.calls.append("coverage")
        return self.receipts


def query(**changes):
    return VoteQuery(PERSON_ID, date(2026, 1, 1), date(2026, 12, 31), **changes)


def test_pagination_keeps_month_choice_and_collective_result_separate():
    repository = Repository([voting(43), voting(42, "no")])
    page = get_person_votes(repository, query(limit=1))
    item = page["items"][0]
    assert item["month"] == "2026-10" and item["occurred_at"] is None
    assert item["individual"] == {"choice": "yes", "participation_status": "voted"}
    assert item["collective_result"] == "approved"
    assert "source_record_id" not in item and "private_document" not in item
    cursor_query = query(cursor=page["next_cursor"])
    assert decode_vote_cursor(cursor_query) == (date(2026, 10, 14), 43)
    assert repository.calls == ["snapshot", "person", "exercises", "votes", "coverage"]


@pytest.mark.parametrize("participation", ["absent", "presiding", "not_recorded", "unknown"])
def test_nonvoting_states_are_not_a_vote_against(participation):
    page = get_person_votes(Repository([voting(choice=None, participation=participation)]), query())
    assert page["items"][0]["individual"] == {"choice": None, "participation_status": participation}


def test_existing_person_without_records_has_unknown_coverage():
    page = get_person_votes(Repository(), query(office_kind="senator"))
    assert page["empty_state"] == "no_linked_vote_records"
    assert page["coverage"]["state"] == "unknown"
    assert page["coverage"]["absence_of_records_is_inactivity"] is False
    assert page["exercise_link_state"] == "unconfirmed"


def test_missing_person_and_foreign_exercise_return_stable_errors():
    for repository, filters, code in [
        (Repository(person=False), {}, "PERSON_NOT_FOUND"),
        (Repository(), {"exercise_id": 999}, "EXERCISE_NOT_FOUND_IN_PERIOD"),
    ]:
        with pytest.raises(PublicProfileError) as error:
            get_person_votes(repository, query(**filters))
        assert error.value.status_code == 404 and error.value.code == code


@pytest.mark.parametrize(
    "changes", [{"limit": 101}, {"limit": True}, {"office_kind": []}, {"exercise_id": -1}]
)
def test_invalid_filters_are_rejected(changes):
    with pytest.raises(PublicProfileError):
        query(**changes)


def test_cursor_is_bound_to_profile_and_filters():
    cursor = encode_vote_cursor(query(), date(2026, 10, 14), 42)
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_vote_cursor(query(cursor=cursor, office_kind="senator"))
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_vote_cursor(query(cursor="invalid%%%%"))


def test_receipt_is_exposed_as_interval_not_complete_career():
    receipt = {
        "institution": "senado",
        "source": "senado",
        "domain": "votes",
        "partition_key": "plenary/2026-10",
        "starts_on": date(2026, 10, 1),
        "ends_before": date(2026, 11, 1),
        "checked_on": date(2026, 10, 17),
        "acquisition_status": "available",
        "identity_verified": True,
        "enumeration_complete": True,
        "source_period_complete": True,
        "artifact_verified": True,
        "scope_verified": True,
    }
    page = get_person_votes(Repository(receipts=[receipt]), query())
    assert page["coverage"]["intervals"][0]["state"] == "verified_for_interval"
    assert page["coverage"]["full_career_verified"] is False


def test_office_filter_without_exercise_hides_unrelated_coverage():
    receipt = {
        "institution": "senado",
        "source": "senado",
        "domain": "votes",
        "partition_key": "plenary/2026-10",
        "starts_on": date(2026, 10, 1),
        "ends_before": date(2026, 11, 1),
        "checked_on": date(2026, 10, 17),
        "acquisition_status": "available",
        "identity_verified": True,
        "enumeration_complete": True,
        "source_period_complete": True,
        "artifact_verified": True,
        "scope_verified": True,
    }
    page = get_person_votes(Repository(receipts=[receipt]), query(office_kind="councillor"))
    assert page["coverage"]["intervals"] == []
    assert page["coverage"]["requested_period_state"] == "not_certified"


def test_public_coverage_channel_never_exposes_arbitrary_partition_keys():
    from service.public_profile.votes import public_coverage_channel

    assert public_coverage_channel("plenary/2026-10") == ("plenary", "plenary/2026-10")
    assert public_coverage_channel("committee/2026-10") == ("committee", "committee/2026-10")
    assert public_coverage_channel("private-person-identification") == ("unknown", None)
