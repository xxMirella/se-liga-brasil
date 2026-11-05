"""Read only public identities; never acquire profile data per URL."""

import re
from uuid import UUID

from service.search_indexing.sitemaps import MAX_SITEMAP_URLS

PUBLIC_PERSON_PREDICATE = """NOT EXISTS (
 SELECT 1 FROM se_liga_brasil.person_identity_alias alias WHERE alias.alias_person_id=p.id)"""


def person_uuid_bounds(prefix):
    if not re.fullmatch(r"[0-9a-f]{1,2}", prefix):
        raise ValueError("INVALID_PERSON_SITEMAP_PREFIX")
    shift = 128 - len(prefix) * 4
    lower = int(prefix, 16) << shift
    upper = (int(prefix, 16) + 1) << shift
    return str(UUID(int=lower)), str(UUID(int=upper)) if upper < 2**128 else None


class SearchIndexRepository:
    def __init__(self, connection):
        self.connection = connection

    def fetch_person_buckets(self):
        return self.connection.execute(
            "SELECT left(p.id::text,2) AS prefix,count(*) AS count "
            "FROM se_liga_brasil.person p WHERE " + PUBLIC_PERSON_PREDICATE
            + " GROUP BY prefix ORDER BY prefix",
        ).fetchall()

    def fetch_people(self, prefix):
        lower, upper = person_uuid_bounds(prefix)
        return self.connection.execute(
            "SELECT p.id::text AS person_id FROM se_liga_brasil.person p "
            "WHERE p.id>=%s::uuid AND (%s::uuid IS NULL OR p.id<%s::uuid) AND "
            + PUBLIC_PERSON_PREDICATE + " ORDER BY p.id LIMIT %s",
            (lower, upper, upper, MAX_SITEMAP_URLS + 1),
        ).fetchall()
