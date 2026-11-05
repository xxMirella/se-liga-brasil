from datetime import date

import pytest

from service.public_profile.contracts import PublicProfileError
from service.public_profile.people_contracts import (
    DEFAULT_PAGE_SIZE,
    PeopleQuery,
    decode_people_cursor,
    encode_people_cursor,
)
from service.public_profile_web.search import render_search_filters, render_search_page

AS_OF = date(2026, 11, 4)
PERSON = "00000000-0000-0000-0000-000000000001"


def test_page_size_is_24_and_sort_defaults_to_name():
    query = PeopleQuery()

    assert DEFAULT_PAGE_SIZE == 24
    assert (query.limit, query.sort) == (24, "name")


def test_unknown_sort_is_rejected():
    with pytest.raises(PublicProfileError, match="INVALID_SORT"):
        PeopleQuery(sort="age")


def test_cursor_carries_the_sort_key_and_is_bound_to_the_sort_mode():
    query = PeopleQuery(sort="party")
    row = {"sort_key": "0PT", "display_name": "Ana", "person_id": PERSON}
    cursor = encode_people_cursor(query, AS_OF, row)

    assert decode_people_cursor(PeopleQuery(sort="party", cursor=cursor), AS_OF) == (
        "0PT", "Ana", PERSON
    )
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_people_cursor(PeopleQuery(sort="state", cursor=cursor), AS_OF)


def test_sort_dropdown_replaces_the_page_size_control():
    html = render_search_filters({"sort": "state"}, ())

    assert "Ordenar por" in html
    assert '<option value="">Nome A–Z</option>' in html
    assert '<option value="party">Partido</option>' in html
    assert '<option value="state" selected>Estado</option>' in html
    assert "Pessoas por página" not in html
    assert 'name="limit"' not in html


def test_more_link_offers_the_next_24_and_the_page_has_no_viewport_measurement():
    results = {"items": [{"person_id": PERSON, "display_name": "Ana"}], "next_cursor": "abc"}
    html = render_search_page({"q": "Ana"}, results)

    assert 'data-people-more>Mostrar mais 24</a>' in html
    assert "cursor=abc" in html
    assert "data-viewport-page" not in html
    assert "Mostrando 1 pessoa" in html


def test_no_more_link_without_a_next_cursor():
    html = render_search_page({}, {"items": [{"person_id": PERSON, "display_name": "Ana"}]})

    assert "Mostrar mais" not in html
