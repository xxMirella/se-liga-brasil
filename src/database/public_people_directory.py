"""Search and party list served from the person_directory dataset, with the canonical fallback.

Same contract as PublicPeopleRepository: rows carry person_id (text), display_name, slug and
sort_key, ordered by the (sort_key, display_name, id) keyset.
"""

import unicodedata

from database.public_people import BASE_ABBREVIATION_SQL, PublicPeopleRepository
from service.serving.release import SERVING_SCHEMA, current_release

DIRECTORY_NAME = "person_directory"
DIRECTORY_TABLE = f"{SERVING_SCHEMA}.{DIRECTORY_NAME}"
SORT_COLUMNS = {"name": None, "party": "party_sort_key", "state": "state_sort_key"}


def normalize_search_term(text):
    """Accent-free lowercase, matching name_search (lower(unaccent(display_name)))."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def like_pattern(text):
    escaped = normalize_search_term(text).replace("\\", "\\\\").replace("%", "\\%")
    return "%" + escaped.replace("_", "\\_") + "%"


def directory_available(connection, as_of):
    release = current_release(connection, DIRECTORY_NAME, as_of)
    return release is not None and release.as_of <= as_of


def open_people_repository(connection, as_of):
    """Directory-backed repository when a fresh release exists, else the canonical one."""
    if directory_available(connection, as_of):
        return DirectoryPeopleRepository(connection)
    return PublicPeopleRepository(connection)


class DirectoryPeopleRepository(PublicPeopleRepository):
    def search_people(self, query, as_of, cursor):
        return search_people_from_directory(self.connection, query, cursor)

    def list_current_political_parties(self, as_of):
        return list_parties_from_directory(self.connection)


def search_people_from_directory(connection, query, cursor):
    sort_column = SORT_COLUMNS[query.sort]
    key_sql = sort_column or "''"
    sort_key, name, identifier = cursor or (None, None, None)
    order = (
        [sort_column, "display_name", "person_id"] if sort_column else ["display_name", "person_id"]
    )
    keyset = ""
    if name is not None:
        values = ["%(after_key)s"] * bool(sort_column) + ["%(after_name)s", "%(after_id)s::uuid"]
        keyset = f"AND ({','.join(order)})>({','.join(values)})"
    return connection.execute(
        f"""SELECT person_id::text AS person_id,display_name,slug,{key_sql} AS sort_key
        FROM {DIRECTORY_TABLE}
        WHERE name_search LIKE %(pattern)s
          AND (%(uf)s::text IS NULL OR %(office_kind)s::text IS NOT NULL
            OR uf @> ARRAY[%(uf)s::text])
          AND (%(office_kind)s::text IS NULL OR %(uf)s::text IS NOT NULL
            OR office_kinds @> ARRAY[%(office_kind)s::text])
          AND (%(uf)s::text IS NULL OR %(office_kind)s::text IS NULL
            OR uf_kinds @> ARRAY[%(uf)s::text||'|'||%(office_kind)s::text])
          AND (%(party)s::text IS NULL OR party_filter @> ARRAY[upper(%(party)s::text)])
          {keyset}
        ORDER BY {",".join(order)}
        LIMIT %(limit)s""",
        {
            "pattern": like_pattern(query.q),
            "uf": query.uf,
            "office_kind": query.office_kind,
            "party": query.political_party,
            "after_key": sort_key,
            "after_name": name,
            "after_id": identifier,
            "limit": query.limit + 1,
        },
    ).fetchall()


def list_parties_from_directory(connection):
    """Parties with at least one person affiliated today, one row per base abbreviation."""
    return connection.execute(
        f"""SELECT cur.abbreviation,min(pp.name) AS name
        FROM (SELECT DISTINCT unnest(parties_current) AS abbreviation FROM {DIRECTORY_TABLE}) cur
        JOIN se_liga_brasil.political_party pp ON {BASE_ABBREVIATION_SQL}=cur.abbreviation
        WHERE pp.abbreviation<>''
        GROUP BY 1 ORDER BY 1"""
    ).fetchall()
