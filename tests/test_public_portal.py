"""Exercise public transport boundaries without database or storage access."""

import json

import pytest

from application.public_portal import dispatch_portal_request
from service.public_profile import PublicProfileError

PERSON_ID = "00000000-0000-0000-0000-000000000001"


class FakeApplication:
    def fetch_people(self, parameters):
        return {"items": [], "received": parameters}

    def fetch_person(self, person_id):
        return {"person_id": person_id}

    def fetch_votes(self, person_id, parameters):
        return {"person_id": person_id, "received": parameters}


def test_search_preserves_encoded_filters():
    response = dispatch_portal_request(FakeApplication(), "/api/people?q=Nome+Completo&uf=SP")
    assert response.status == 200
    assert json.loads(response.body)["received"] == {"q": "Nome Completo", "uf": "SP"}


@pytest.mark.parametrize("query", ["q=a&q=b", "unknown=x", "limit=1&limit=2"])
def test_rejects_ambiguous_or_unknown_filters(query):
    response = dispatch_portal_request(FakeApplication(), "/api/people?" + query)
    assert response.status == 400


def test_votes_preserve_snapshot_cursor():
    target = f"/api/people/{PERSON_ID}/votes?cursor=opaque%2Bvalue&start_date=2026-10-14"
    response = dispatch_portal_request(FakeApplication(), target)
    assert json.loads(response.body)["received"]["cursor"] == "opaque+value"


def test_stylesheet_does_not_access_data_sources():
    response = dispatch_portal_request(object(), "/assets/public-profile.css")
    assert response.status == 200
    assert response.content_type.startswith("text/css")
    assert response.body


def test_private_exception_is_not_exposed():
    class UnavailableApplication:
        def fetch_people(self, parameters):
            raise RuntimeError("private credential or connection detail")

    response = dispatch_portal_request(UnavailableApplication(), "/api/people")
    assert response.status == 503
    assert json.loads(response.body) == {"error": "TEMPORARILY_UNAVAILABLE"}


def test_html_errors_remain_navigable_html():
    class MissingApplication:
        def fetch_people(self, parameters):
            raise PublicProfileError("PERSON_NOT_FOUND", 404)

    response = dispatch_portal_request(MissingApplication(), "/pessoas?limit=6")
    assert response.status == 404
    assert response.content_type.startswith("text/html")
    assert b"PERSON_NOT_FOUND" not in response.body
