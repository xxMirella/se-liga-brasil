from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event

import pytest

from service.public_profile.people_contracts import PeopleQuery
from service.public_profile.search_cache import PublicSearchCache


def test_cache_reuses_projection_without_mutable_sharing_and_expires():
    now = [0]
    cache = PublicSearchCache(clock=lambda: now[0])
    calls = []

    def load():
        calls.append(1)
        return {"items": [{"display_name": "Pessoa"}]}

    result = cache.get_or_load("key", load)
    result["items"].clear()
    assert len(cache.get_or_load("key", load)["items"]) == 1
    assert len(calls) == 1
    now[0] = 30
    cache.get_or_load("key", load)
    assert len(calls) == 2
    cache.clear()
    cache.get_or_load("key", load)
    assert len(calls) == 3


@pytest.mark.parametrize("kwargs", [{"ttl_seconds": 0}, {"capacity": 0}, {"max_bytes": 0}])
def test_invalid_cache_limits(kwargs):
    with pytest.raises(ValueError):
        PublicSearchCache(**kwargs)


def test_cache_capacity_and_bytes_are_bounded():
    cache = PublicSearchCache(capacity=1, max_bytes=100)
    cache.get_or_load("first", lambda: {"value": 1})
    cache.get_or_load("second", lambda: {"value": 2})
    assert len(cache._entries) == 1
    assert "first" not in cache._entries
    cache.get_or_load("large", lambda: {"value": "x" * 101})
    assert "large" not in cache._entries
    assert cache._bytes <= 100
    small = PublicSearchCache(max_bytes=20)
    small.get_or_load("one", lambda: {"value": 1})
    small.get_or_load("two", lambda: {"value": 2})
    assert list(small._entries) == ["two"]


def test_query_key_isolates_all_filters_page_sizes_cursors_and_dates():
    cache = PublicSearchCache()
    queries = [PeopleQuery(), PeopleQuery(q="Nome"), PeopleQuery(uf="SP"),
               PeopleQuery(office_kind="senator"), PeopleQuery(political_party="PT"),
               PeopleQuery(limit=12), PeopleQuery(cursor="cursor")]
    keys = [(query, date(2026, 10, 19)) for query in queries]
    keys.append((PeopleQuery(), date(2026, 10, 20)))
    for index, key in enumerate(keys):
        assert cache.get_or_load(key, lambda value=index: {"value": value}) == {"value": index}
    assert len(cache._entries) == len(keys)


def test_concurrent_identical_requests_load_once():
    cache = PublicSearchCache()
    started, release = Event(), Event()
    calls = []

    def load():
        calls.append(1)
        started.set()
        assert release.wait(2)
        return {"items": []}

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get_or_load, "key", load)
        assert started.wait(2)
        second = pool.submit(cache.get_or_load, "key", load)
        release.set()
        assert first.result() == second.result() == {"items": []}
    assert len(calls) == 1


def test_loader_failure_is_not_cached():
    cache = PublicSearchCache()
    with pytest.raises(RuntimeError):
        cache.get_or_load("key", lambda: (_ for _ in ()).throw(RuntimeError()))
    assert cache.get_or_load("key", lambda: {"ok": True}) == {"ok": True}


def test_portal_search_cache_avoids_connection_on_hit(monkeypatch):
    from contextlib import nullcontext

    from application.public_portal import PublicPortalApplication

    connections, searches = [], []
    monkeypatch.setattr(
        "database.operations.connect_database",
        lambda *_: connections.append(1) or nullcontext(object()),
    )
    monkeypatch.setattr(
        "service.public_profile.people.search_people",
        lambda _r, query, _d: searches.append(query) or {"items": []},
    )
    app = PublicPortalApplication(None, None, today=lambda: date(2026, 10, 19))
    app.fetch_people({})
    app.fetch_people({})
    assert len(connections) == len(searches) == 1
    assert searches[0].limit == 6
    app.fetch_people({"uf": "SP"})
    assert len(connections) == len(searches) == 2


def test_sql_fetches_only_page_plus_one_without_offset():
    from types import SimpleNamespace

    from database.public_people import PublicPeopleRepository

    calls = []
    connection = SimpleNamespace(execute=lambda sql, parameters: (
        calls.append((sql, parameters)) or SimpleNamespace(fetchall=lambda: [])
    ))
    PublicPeopleRepository(connection).search_people(PeopleQuery(), date(2026, 10, 19), None)
    assert calls[0][1][-1] == 7
    assert "OFFSET" not in calls[0][0]
    assert "SELECT p.id::text AS person_id,p.display_name,p.slug" in calls[0][0]


def test_html_shell_never_queries_database_and_keeps_filter_fallback():
    from application.public_portal import dispatch_portal_request

    response = dispatch_portal_request(object(), "/pessoas?q=Nome&uf=SP")
    assert response.status == 200
    html = response.body.decode()
    assert 'data-viewport-page' in html
    assert '/assets/people-viewport.js' in html
    assert 'q=Nome&amp;uf=SP&amp;limit=6' in html
    assert 'Carregar 6 pessoas por página' in html
    assert dispatch_portal_request(object(), "/pessoas?q=x").status == 400


def test_viewport_asset_is_local_bounded_and_has_no_resize_requests():
    from application.public_portal import dispatch_portal_request

    response = dispatch_portal_request(object(), "/assets/people-viewport.js")
    assert response.status == 200
    assert response.content_type.startswith("text/javascript")
    script = response.body.decode()
    assert 'Math.min(24' in script
    assert 'Math.max(1' in script
    assert 'getBoundingClientRect().top' in script
    assert 'location.replace' in script
    assert 'addEventListener' not in script
    assert dispatch_portal_request(object(), "/assets/people-viewport.js?x=1").status == 404


def test_shell_and_results_keep_filters_collapsed_and_same_measured_header():
    from service.public_profile_web.search import render_search_page, render_search_shell

    filters = {"q": "Nome", "uf": "SP"}
    shell = render_search_shell(filters)
    page = render_search_page({**filters, "limit": "3"}, {"items": []})
    for html in (shell, page):
        assert '<details class="people-filters"><summary>Filtrar pessoas · 2 filtros ativos' in html
        assert '<details class="people-filters" open' not in html
        assert '<h1>Resultados da busca</h1>' in html
        assert 'Identidade, vínculos e atuação disponíveis nas fontes consultadas.' in html
        assert 'value="Nome"' in html
    default_shell = render_search_shell({})
    default_page = render_search_page({"limit": "3"}, {"items": []})
    assert '<h1>Conheça as trajetórias públicas</h1>' in default_shell
    assert '<h1>Conheça as trajetórias públicas</h1>' in default_page
