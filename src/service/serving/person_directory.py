"""person_directory: one row per public person, ready for the search without joins.

The build reuses the canonical rules of database.public_people (alias exclusion, current
affiliation, base party abbreviation, current mandate, sort keys), evaluated at `as_of`.
`unaccent` runs only here, never at read time.
"""

from datetime import date

from database.public_people import (
    BASE_ABBREVIATION_SQL,
    CURRENT_AFFILIATION_FILTER,
    LATEST_AFFILIATION_PREDICATE,
    SORT_KEY_SQL,
)
from service.serving.builder import DatasetSpec

DATASET_NAME = "person_directory"

COLUMNS_DDL = """person_id uuid PRIMARY KEY, slug text NOT NULL, display_name text NOT NULL,
  name_search text NOT NULL, uf text[] NOT NULL, office_kinds text[] NOT NULL,
  uf_kinds text[] NOT NULL, party_abbr text, party_filter text[] NOT NULL,
  parties_current text[] NOT NULL, photo text, party_sort_key text NOT NULL,
  state_sort_key text NOT NULL, as_of date NOT NULL"""

INDEXES = (
    "(party_sort_key, display_name, person_id)",
    "(state_sort_key, display_name, person_id)",
    "(display_name, person_id)",
    "USING gin (uf)",
    "USING gin (office_kinds)",
    "USING gin (uf_kinds)",
    "USING gin (party_filter)",
)

# Current mandates of p. uf/office_kinds answer single filters; uf_kinds ("SP|senator") keeps the
# pairing so that uf+office_kind together still require the SAME mandate, as the canonical SQL does.
_CURRENT_TERMS = """FROM se_liga_brasil.office_term t
    JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
    WHERE t.person_id=p.id AND e.starts_on<=%(as_of)s
    AND (e.ends_before IS NULL OR e.ends_before>%(as_of)s)"""

_INSERT_SQL = f"""INSERT INTO {{table}}(person_id,slug,display_name,name_search,uf,office_kinds,
  uf_kinds,party_abbr,party_filter,parties_current,photo,party_sort_key,state_sort_key,as_of)
SELECT person_id,slug,display_name,lower(unaccent(display_name)),uf,office_kinds,uf_kinds,
  CASE WHEN left(party_sort_key,1)='0' THEN substr(party_sort_key,2) END,
  party_filter,parties_current,photo,party_sort_key,state_sort_key,%(as_of)s
FROM (
  SELECT p.id AS person_id,p.slug,p.display_name,p.photo_url AS photo,
    ARRAY(SELECT DISTINCT t.represented_uf {_CURRENT_TERMS}
      AND t.represented_uf IS NOT NULL ORDER BY 1) AS uf,
    ARRAY(SELECT DISTINCT t.office_kind {_CURRENT_TERMS}
      AND t.office_kind IS NOT NULL ORDER BY 1) AS office_kinds,
    ARRAY(SELECT DISTINCT t.represented_uf||'|'||t.office_kind {_CURRENT_TERMS}
      AND t.represented_uf IS NOT NULL AND t.office_kind IS NOT NULL ORDER BY 1) AS uf_kinds,
    ARRAY(SELECT DISTINCT {BASE_ABBREVIATION_SQL}
      FROM se_liga_brasil.political_party_affiliation a
      JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
      WHERE {LATEST_AFFILIATION_PREDICATE} ORDER BY 1) AS party_filter,
    ARRAY(SELECT DISTINCT {BASE_ABBREVIATION_SQL}
      FROM se_liga_brasil.political_party_affiliation a
      JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
      WHERE {CURRENT_AFFILIATION_FILTER} AND pp.abbreviation<>'' ORDER BY 1) AS parties_current,
    {SORT_KEY_SQL["party"]} AS party_sort_key,
    {SORT_KEY_SQL["state"]} AS state_sort_key
  FROM se_liga_brasil.person p
  WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
    WHERE a.alias_person_id=p.id)
) directory"""


def person_directory_insert_sql(as_of: date) -> str:
    """INSERT..SELECT with the date inlined: the builder runs it without bind parameters."""
    return _INSERT_SQL.replace("%(as_of)s", f"DATE '{as_of.isoformat()}'")


def person_directory_spec(connection, as_of: date) -> DatasetSpec:
    return DatasetSpec(
        name=DATASET_NAME,
        columns_ddl=COLUMNS_DDL,
        indexes=INDEXES,
        insert_sql=person_directory_insert_sql(as_of),
    )
