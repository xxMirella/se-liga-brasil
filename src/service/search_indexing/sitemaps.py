"""Bounded XML discovery of canonical public pages and stable UUID-range shards."""

from collections import defaultdict
from datetime import date, datetime
from xml.etree import ElementTree

from service.search_indexing.configuration import public_site_origin, search_indexing_enabled

NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_SITEMAP_URLS = 50_000
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
PERSON_SHARD_TARGET = 5_000
STATIC_PATHS = (
    "/", "/panorama", "/pessoas", "/fontes-dos-dados", "/comparacao-de-classificacoes",
    "/como-funciona",
    "/como-funciona?esfera=estadual", "/como-funciona?esfera=federal",
    "/como-funciona?esfera=distrital", "/como-funciona?esfera=todos",
)


class SitemapCapacityError(RuntimeError):
    """An oversized publication must fail as a server error, never return a partial sitemap."""


def person_sitemap_prefixes(buckets):
    groups = defaultdict(list)
    for row in buckets:
        groups[row["prefix"][0]].append(row)
    return [prefix for group, rows in sorted(groups.items())
            for prefix in ([group] if sum(row["count"] for row in rows) <= PERSON_SHARD_TARGET
                           else [row["prefix"] for row in rows])]


def sitemap_index_paths(catalog):
    return ["/sitemaps/pages.xml", *[
        f"/sitemaps/people-{prefix}.xml"
        for prefix in person_sitemap_prefixes(catalog["person_buckets"])
    ]]


def sitemap_timestamp(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError("SITEMAP_LASTMOD_REQUIRES_A_PUBLICATION_TIMESTAMP")


def render_sitemap(entries, *, index=False):
    if len(entries) > MAX_SITEMAP_URLS:
        raise SitemapCapacityError("SITEMAP_URL_LIMIT_EXCEEDED")
    root = ElementTree.Element("sitemapindex" if index else "urlset", xmlns=NAMESPACE)
    origin = public_site_origin()
    for entry in entries:
        child = ElementTree.SubElement(root, "sitemap" if index else "url")
        ElementTree.SubElement(child, "loc").text = origin + entry["path"]
        if entry.get("lastmod") is not None:
            ElementTree.SubElement(child, "lastmod").text = sitemap_timestamp(entry["lastmod"])
    content = ElementTree.tostring(root, encoding="unicode", xml_declaration=True)
    if len(content.encode("utf-8")) > MAX_SITEMAP_BYTES:
        raise SitemapCapacityError("SITEMAP_BYTE_LIMIT_EXCEEDED")
    return content


def render_robots():
    lines = ["User-agent: *", "Allow: /", "Disallow: /api/", "Disallow: /api"]
    if search_indexing_enabled():
        lines.extend(["", "Sitemap: " + public_site_origin() + "/sitemap.xml"])
    return "\n".join(lines) + "\n"
