"""Connect public sitemap reads and metadata rendering to the existing HTTP application."""

import re
from dataclasses import replace
from datetime import date

from service.search_indexing.metadata import enrich_public_html
from service.search_indexing.sitemaps import (
    STATIC_PATHS,
    render_robots,
    render_sitemap,
    sitemap_index_paths,
)

PERSON_SITEMAP = re.compile(r"/sitemaps/people-([0-9a-f]{1,2})\.xml")


def enrich_search_response(response, target, application):
    if not response.content_type.startswith("text/html"):
        return response
    today = application.today() if hasattr(application, "today") else date.today()
    return replace(response, body=enrich_public_html(
        response.body, target, today, response.status, indexable=response.search_indexable,
    ).encode("utf-8"))


def route_search_index_request(application, parsed):
    from application.public_portal import encode_response

    if parsed.path == "/robots.txt" and not parsed.query:
        return encode_response(render_robots(), content_type="text/plain")
    if parsed.query:
        return None
    if parsed.path == "/sitemap.xml":
        catalog = application.search_index.catalog()
        content = render_sitemap(
            [{"path": path} for path in sitemap_index_paths(catalog)], index=True,
        )
    elif parsed.path == "/sitemaps/pages.xml":
        content = render_sitemap([{"path": path} for path in STATIC_PATHS])
    else:
        return route_entity_sitemap(application, parsed.path)
    return encode_response(content, content_type="application/xml")


def route_entity_sitemap(application, path):
    from application.public_portal import encode_response

    if match := PERSON_SITEMAP.fullmatch(path):
        people = application.search_index.people(match[1])
        content = render_sitemap([{"path": "/pessoas/" + row["person_id"]} for row in people])
        return encode_response(content, content_type="application/xml")
    return None


class SearchIndexReader:
    def __init__(self, connections, today):
        from service.public_profile.search_cache import PublicSearchCache

        self.connections, self.today = connections, today
        self.catalog_cache = PublicSearchCache(ttl_seconds=60, capacity=2)

    def catalog(self):
        return self.catalog_cache.get_or_load(self.today().year, self._load_catalog)

    def _load_catalog(self):
        from database.search_indexing import SearchIndexRepository

        def read(connection):
            repository = SearchIndexRepository(connection)
            return {"person_buckets": repository.fetch_person_buckets()}

        return self.connections.read(read)

    def people(self, prefix):
        from database.search_indexing import SearchIndexRepository

        return self.connections.read(
            lambda connection: SearchIndexRepository(connection).fetch_people(prefix),
        )
