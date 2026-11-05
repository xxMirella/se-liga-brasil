"""Discovery and canonicalization preserve meaningful public pages and real timestamps."""

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from application.public_cache import prepare_public_response
from application.public_portal import dispatch_portal_request
from database.search_indexing import person_uuid_bounds
from service.search_indexing.canonical import canonical_page
from service.search_indexing.configuration import public_site_origin
from service.search_indexing.metadata import enrich_public_html
from service.search_indexing.sitemaps import (
    NAMESPACE,
    person_sitemap_prefixes,
    render_sitemap,
)

TODAY = date(2026, 11, 2)
PERSON_ID = "00000000-0000-0000-0000-000000000001"
ORIGIN = "https://seligabrasil.gov"


@pytest.fixture(autouse=True)
def production_origin(monkeypatch):
    monkeypatch.setenv("PUBLIC_SITE_URL", ORIGIN)
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("SEARCH_INDEXING_ENABLED", "true")


def sitemap_locations(body):
    return [item.text for item in ElementTree.fromstring(body).iter("{" + NAMESPACE + "}loc")]


def application_stub():
    return SimpleNamespace(today=lambda: TODAY, search_index=SimpleNamespace(
        catalog=lambda: {"person_buckets": [{"prefix": "00", "count": 1}],
                         },
        people=lambda prefix: [{"person_id": PERSON_ID}],
    ))


@pytest.mark.parametrize("target,expected", [
    ("/sobre/", "/"),
    ("/pessoas?limit=24", "/pessoas"),
    (f"/pessoas/{PERSON_ID}?tab=profile", f"/pessoas/{PERSON_ID}"),
    (f"/pessoas/{PERSON_ID}?tab=activity&scope=history", f"/pessoas/{PERSON_ID}?tab=activity"),
    ("/panorama", "/panorama"),
    ("/panorama?leg=2019", "/panorama?leg=2019"),
    ("/panorama?leg=2019&house=senado&mode=bloco&hl=PT&scen=conc&prop=A&view=bloco&bloc=left",
     "/panorama?leg=2019"),
    ("/panorama?house=senado&mode=bloco", "/panorama"),
])
def test_semantic_canonical_urls(target, expected):
    assert canonical_page(target, TODAY) == (expected, False)


def test_each_legislature_is_a_distinct_canonical_page_and_interactions_collapse():
    urls = {canonical_page(target, TODAY)[0] for target in (
        "/panorama?leg=2015", "/panorama?leg=2019", "/panorama?leg=2019&house=senado",
        "/panorama?leg=2019&mode=bloco&hl=PT", "/panorama", "/panorama?house=senado",
    )}
    assert urls == {"/panorama?leg=2015", "/panorama?leg=2019", "/panorama"}


def test_panorama_is_indexable_even_with_interaction_parameters():
    assert canonical_page("/panorama?leg=2019&house=senado", TODAY)[1] is False


def test_panorama_metadata_describes_the_majority_question():
    body = b'<html><head><title>Panorama</title></head></html>'
    result = enrich_public_html(body, "/panorama", TODAY)
    assert "<title>Panorama político: quem tem a maioria? · Se Liga, Brasil</title>" in result
    assert '<link rel="canonical" href="' + ORIGIN + '/panorama">' in result
    with_legislature = enrich_public_html(body, "/panorama?leg=2019&house=senado", TODAY)
    assert "Legislatura 2019–2022" in with_legislature
    assert ORIGIN + "/panorama?leg=2019" in with_legislature


def test_pages_sitemap_lists_panorama_without_territory_or_year_urls():
    response = dispatch_portal_request(application_stub(), "/sitemaps/pages.xml")
    locations = sitemap_locations(response.body)
    assert ORIGIN + "/panorama" in locations
    assert not any("/panorama?" in location for location in locations)
    assert dispatch_portal_request(application_stub(), "/sitemaps/panorama-BR.xml").status == 404


def test_party_case_variants_share_a_canonical_url():
    assert canonical_page("/comparacao-de-classificacoes?partido=PL", TODAY) == (
        canonical_page("/comparacao-de-classificacoes?partido=pl", TODAY)
    )


def test_capacity_overflow_is_a_server_error_and_never_a_truncated_sitemap(monkeypatch):
    from service.search_indexing import sitemaps

    monkeypatch.setattr(sitemaps, "MAX_SITEMAP_URLS", 1)
    app = application_stub()
    app.search_index.people = lambda _: [{"person_id": PERSON_ID}, {"person_id": PERSON_ID}]
    response = dispatch_portal_request(app, "/sitemaps/people-0.xml")
    assert response.status == 503
    assert b"<urlset" not in response.body


def test_empty_dashboard_can_be_served_without_claiming_indexable_content():
    result = enrich_public_html(b'<html><head><title>Panorama</title></head></html>',
                                "/panorama", TODAY, indexable=False)
    assert 'content="noindex, follow"' in result


def test_xml_escapes_and_preserves_real_publication_date():
    published = datetime(2026, 10, 29, 17, 39, tzinfo=UTC)
    content = render_sitemap([{"path": "/panorama?leg=2019&house=senado", "lastmod": published}])
    assert "&amp;" in content
    assert "2026-10-29T17:39:00+00:00" in content
    assert "changefreq" not in content and "priority" not in content
    assert "lastmod" not in render_sitemap([{"path": f"/pessoas/{PERSON_ID}"}])


def test_person_shards_split_only_dense_prefixes_and_cover_uuid_extremes():
    assert person_sitemap_prefixes([{"prefix": "00", "count": 2},
                                    {"prefix": "01", "count": 3}]) == ["0"]
    assert person_sitemap_prefixes([{"prefix": "00", "count": 4_000},
                                    {"prefix": "01", "count": 2_000}]) == ["00", "01"]
    assert person_uuid_bounds("0") == ("00000000-0000-0000-0000-000000000000",
                                       "10000000-0000-0000-0000-000000000000")
    assert person_uuid_bounds("ff")[1] is None
    with pytest.raises(ValueError, match="PREFIX"):
        person_uuid_bounds("../../")


def test_sitemap_index_and_children_use_the_same_origin_and_routes():
    app = application_stub()
    index = dispatch_portal_request(app, "/sitemap.xml")
    assert index.status == 200
    assert index.content_type.startswith("application/xml")
    locations = sitemap_locations(index.body)
    assert locations == [ORIGIN + path for path in (
        "/sitemaps/pages.xml", "/sitemaps/people-0.xml",
    )]
    for location in locations:
        child = dispatch_portal_request(app, location.removeprefix(ORIGIN))
        assert child.status == 200
        assert all(url.startswith(ORIGIN + "/") for url in sitemap_locations(child.body))
    assert dispatch_portal_request(app, "/sitemaps/people-xyz.xml").status == 404


def test_new_public_identity_appears_without_a_static_file_or_redeploy():
    app = application_stub()
    records = [{"person_id": PERSON_ID}]
    app.search_index.people = lambda prefix: records
    first = dispatch_portal_request(app, "/sitemaps/people-0.xml")
    records.append({"person_id": "00000000-0000-0000-0000-000000000002"})
    second = dispatch_portal_request(app, "/sitemaps/people-0.xml")
    assert len(sitemap_locations(first.body)) == 1
    assert len(sitemap_locations(second.body)) == 2
    _, _, first_headers = prepare_public_response("/sitemaps/people-0.xml", 200, first.body, {})
    status, body, _ = prepare_public_response("/sitemaps/people-0.xml", 200, second.body,
                                             {"If-None-Match": first_headers["ETag"]})
    assert status == 200 and body == second.body


def test_metadata_is_in_initial_html_and_prevents_script_injection():
    name = 'Nome &lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;'
    body = f'<html><head><title>{name} · Se Liga, Brasil</title></head><body></body></html>'
    result = enrich_public_html(body.encode(), f"/pessoas/{PERSON_ID}", TODAY)
    assert '<link rel="canonical" href="' + ORIGIN in result
    assert '<meta name="description"' in result
    assert '<meta property="og:title"' in result
    raw = result.split('<script type="application/ld+json">')[1].split('</script>')[0]
    structured = json.loads(raw)
    assert structured["@graph"][1]["mainEntity"]["@type"] == "Person"
    assert "<script>alert(1)</script>" not in result


def test_errors_search_facets_and_previews_are_noindex(monkeypatch):
    app = application_stub()
    app.fetch_people = lambda parameters: {"items": []}
    assert b'content="noindex, follow"' in dispatch_portal_request(app, "/pessoas?q=Nome").body
    assert b'content="noindex, follow"' in dispatch_portal_request(app, "/pessoas?unknown=x").body
    monkeypatch.setenv("VERCEL_ENV", "preview")
    page = dispatch_portal_request(app, "/")
    assert b'content="noindex, follow"' in page.body
    assert b'Sitemap:' not in dispatch_portal_request(app, "/robots.txt").body
    headers = prepare_public_response("/", 200, page.body, {})[2]
    assert headers["X-Robots-Tag"] == "noindex, follow"


def test_configured_origin_never_accepts_credentials_paths_or_injection(monkeypatch):
    for value in ("http://example.com", "https://a:b@example.com", "https://example.com/path",
                  'https://example.com/\" onload=\"x', "https://example.com?x=1"):
        monkeypatch.setenv("PUBLIC_SITE_URL", value)
        with pytest.raises(ValueError):
            public_site_origin()
