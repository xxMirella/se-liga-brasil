"""Public profiles disclose only approved fields and distinguish observations from current facts."""

from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from service.public_profile.contracts import PublicProfileError
from service.public_profile.people import (
    PeopleQuery,
    completed_tenure,
    get_public_person,
    public_age,
    public_exercises,
    public_office_status,
    public_payments,
    public_photo,
    public_political_party,
    search_people,
)
from service.public_profile.people_contracts import decode_people_cursor

TODAY = date(2026, 10, 18)
PERSON_ID = str(uuid4())


class PeopleRepository:
    def __init__(self):
        self.calls = []
        self.person = {
            "person_id": PERSON_ID,
            "display_name": "Nome público",
            "slug": "nome",
            "birth_date": date(1990, 10, 19),
            "cpf": "PRIVATE",
            "civil_name": "PRIVATE",
        }
        self.rows = [{"person_id": PERSON_ID, "display_name": "Nome público", "slug": "nome"}]

    def read_snapshot(self):
        return nullcontext()

    def search_people(self, query, as_of, cursor):
        self.calls.append(cursor)
        return self.rows

    def fetch_public_person(self, person_id):
        return self.person

    def fetch_current_exercises(self, person_id, as_of):
        return []

    def fetch_public_affiliations(self, person_id, as_of):
        return []

    def fetch_latest_public_payments(self, person_id, as_of):
        return []


def test_profile_never_discloses_private_identity_and_does_not_invent_zeroes():
    profile = get_public_person(PeopleRepository(), PERSON_ID, TODAY)
    assert profile["age"] == {"value": 35, "status": "known"}
    assert "PRIVATE" not in str(profile)
    assert "birth_date" not in str(profile)
    assert profile["payments"] == []
    assert profile["public_office"]["has_current_public_office"] is None
    assert profile["political_party"]["status"] == "unknown"
    assert profile["photo"]["url"] is None


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/a",
        "javascript:alert(1)",
        "https://camara.leg.br.evil.example/a",
        "https://user@camara.leg.br/a",
        "http://camara.leg.br/a",
        "https://camara.leg.br:abc/a",
    ],
)
def test_photos_reject_non_official_or_unsafe_urls(url):
    assert public_photo(url)["url"] is None


def test_official_photo_and_age_boundaries():
    assert public_photo("https://www.camara.leg.br/photo.jpg")["status"] == "available"
    assert public_age(date(1990, 10, 18), TODAY)["value"] == 36
    assert public_age(date(2030, 1, 1), TODAY)["value"] is None
    assert public_age(date(2000, 2, 29), date(2025, 2, 28))["value"] == 24
    assert public_age(date(2000, 2, 29), date(2025, 3, 1))["value"] == 25
    assert completed_tenure(date(2024, 1, 31), date(2025, 2, 28)) == {
        "years": 1,
        "months": 1,
        "status": "known",
    }


def test_affiliation_observation_is_not_legal_membership():
    row = {
        "abbreviation": "XYZ",
        "name": "Partido demonstrativo",
        "observed_on": date(2026, 10, 1),
        "evidence_kind": "electoral_declaration",
    }
    assert public_political_party([row])["status"] == "electoral_declaration"
    conflicting = {**row, "abbreviation": "ABC"}
    assert public_political_party([row, conflicting])["status"] == "conflicting"


def test_stale_payroll_is_not_current_salary_and_decimals_are_strings():
    row = {
        "organization_code": "camara",
        "office_kind": "federal_deputy",
        "payroll_kind": "normal",
        "competence": date(2025, 1, 1),
        "currency": "BRL",
        "gross_amount": Decimal("100.00"),
        "tax_amount": Decimal("10.00"),
        "net_amount": Decimal("90.00"),
    }
    payment = public_payments([row], TODAY)[0]
    assert payment["freshness"] == "outdated"
    assert payment["gross_amount"] == "100.00"
    assert (
        public_payments([{**row, "competence": date(2026, 10, 1)}], TODAY)[0]["freshness"]
        == "current_competence"
    )


def test_search_cursor_is_bound_to_filters_and_reference_date():
    repository = PeopleRepository()
    repository.rows *= 2
    page = search_people(repository, PeopleQuery(q="Nome", limit=1), TODAY)
    cursor = page["next_cursor"]
    assert decode_people_cursor(PeopleQuery(q="Nome", cursor=cursor), TODAY)[1] == PERSON_ID
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        search_people(repository, PeopleQuery(q="Outra", cursor=cursor), TODAY)
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        search_people(repository, PeopleQuery(q="Nome", cursor=cursor), date(2026, 10, 19))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"q": "a"},
        {"q": "a" * 121},
        {"limit": True},
        {"limit": 101},
        {"uf": "XX"},
        {"office_kind": "bad"},
        {"political_party": "';DROP"},
    ],
)
def test_search_filters_are_bounded(kwargs):
    with pytest.raises(PublicProfileError):
        PeopleQuery(**kwargs)


def test_invalid_or_unknown_person_fails_before_reading_other_facts():
    repository = PeopleRepository()
    with pytest.raises(PublicProfileError, match="INVALID_PERSON_ID"):
        get_public_person(repository, "invalid", TODAY)
    repository.person = None
    with pytest.raises(PublicProfileError, match="PERSON_NOT_FOUND"):
        get_public_person(repository, PERSON_ID, TODAY)


def test_overlapping_exercises_do_not_double_count_tenure():
    exercise = {
        "exercise_id": 1,
        "term_id": 1,
        "office_kind": "senator",
        "represented_uf": "SP",
        "institution_code": "senado",
        "institution_name": "Senado",
        "starts_on": date(2025, 1, 1),
    }
    rows = public_exercises([exercise, {**exercise, "exercise_id": 2}], TODAY)
    assert all(row["tenure"]["years"] is None for row in rows)
    assert all(row["tenure"]["status"] == "overlapping_exercises" for row in rows)


def test_old_office_snapshot_does_not_establish_new_start_date():
    person = {
        "has_current_public_office": True,
        "current_public_office_kind": "senator",
        "public_office_status_as_of": date(2026, 1, 1),
        "snapshot_institution_code": "senado",
        "snapshot_institution_name": "Senado",
    }
    status = public_office_status(person, [], TODAY)
    assert status["status"] == "historical_observation"
    assert status["office_kind"] == "senator"
    assert "starts_on" not in status
