"""Batch ingestion and public reads of immutable documentary legal-scope versions."""

import json
from uuid import UUID

from service.office_duties.legal_catalog import scope_record_hash

RECORD_COLUMNS = """
 office_kind text,jurisdiction text,catalog_version text,reviewed_on date,
 legal_valid_from date,legal_valid_until date,coverage_status text,
 competencies jsonb,restrictions jsonb,sources jsonb,limitations text[],content_sha256 text
"""


def ingest_office_legal_scopes(connection, records):
    """Insert a bounded batch; replay is a no-op and altered same-version content aborts."""
    prepared = prepare_scope_records(records)
    if not prepared:
        return {"inserted": 0, "unchanged": 0}
    payload = json.dumps(list(prepared.values()), ensure_ascii=False)
    with connection.transaction():
        connection.execute("SET LOCAL statement_timeout='30s'")
        inserted = connection.execute(
            f"""INSERT INTO se_liga_brasil.office_legal_scope_version (
             office_kind,jurisdiction,catalog_version,reviewed_on,legal_valid_from,
             legal_valid_until,coverage_status,competencies,restrictions,sources,
             limitations,content_sha256)
             SELECT * FROM jsonb_to_recordset(%s::jsonb) AS incoming({RECORD_COLUMNS})
             ON CONFLICT(office_kind,jurisdiction,catalog_version) DO NOTHING
             RETURNING office_kind""",
            (payload,),
        ).fetchall()
        stored = connection.execute(
            f"""SELECT existing.office_kind,existing.jurisdiction,existing.catalog_version,
             existing.content_sha256 FROM se_liga_brasil.office_legal_scope_version existing
             JOIN jsonb_to_recordset(%s::jsonb) AS incoming({RECORD_COLUMNS})
             USING(office_kind,jurisdiction,catalog_version)""",
            (payload,),
        ).fetchall()
        verify_stored_hashes(prepared, stored)
    return {"inserted": len(inserted), "unchanged": len(prepared) - len(inserted)}


def prepare_scope_records(records):
    prepared = {}
    for record in records:
        if record["content_sha256"] != scope_record_hash(record):
            raise ValueError("OFFICE_SCOPE_HASH_INVALID")
        key = scope_key(record)
        previous = prepared.get(key)
        if previous and previous["content_sha256"] != record["content_sha256"]:
            raise ValueError("OFFICE_SCOPE_VERSION_CONFLICT")
        prepared[key] = record
    return prepared


def scope_key(record):
    return record["office_kind"], record["jurisdiction"], record["catalog_version"]


def verify_stored_hashes(prepared, stored):
    if len(stored) != len(prepared):
        raise ValueError("OFFICE_SCOPE_BATCH_INCOMPLETE")
    for record in stored:
        if prepared[scope_key(record)]["content_sha256"] != record["content_sha256"]:
            raise ValueError("OFFICE_SCOPE_VERSION_CONFLICT")


PERSON_SCOPE_SQL = """
 WITH observed_offices AS (
  SELECT office_kind,represented_uf FROM se_liga_brasil.office_term WHERE person_id=%s
  UNION
  SELECT CASE
   WHEN lower(office_name)='deputado federal' THEN 'federal_deputy'
   WHEN lower(office_name)='deputado estadual' THEN 'state_deputy'
   WHEN lower(office_name)='deputado distrital' THEN 'district_deputy'
   WHEN lower(office_name)='senador' THEN 'senator'
   WHEN lower(office_name) LIKE '%%suplente%%' THEN 'senator_substitute'
   WHEN lower(office_name)='governador' THEN 'governor'
   WHEN lower(office_name)='vice-governador' THEN 'vice_governor'
   WHEN lower(office_name)='prefeito' THEN 'mayor'
   WHEN lower(office_name)='vice-prefeito' THEN 'vice_mayor'
   WHEN lower(office_name)='vereador' THEN 'councillor'
   ELSE 'other' END,represented_uf
  FROM se_liga_brasil.electoral_candidacy WHERE person_id=%s
 ), scopes AS (
  SELECT DISTINCT office_kind,CASE
   WHEN office_kind IN ('state_deputy','governor','vice_governor') THEN represented_uf
   WHEN office_kind='district_deputy' THEN 'DF' ELSE 'BR' END AS jurisdiction
  FROM observed_offices
 )
 SELECT scopes.office_kind,scopes.jurisdiction,legal.catalog_version,legal.reviewed_on,
  legal.legal_valid_from,legal.legal_valid_until,
  coalesce(legal.coverage_status,'unclassified') AS coverage_status,
  coalesce(legal.competencies,'[]'::jsonb) AS competencies,
  coalesce(legal.restrictions,'[]'::jsonb) AS restrictions,
  coalesce(legal.sources,'[]'::jsonb) AS sources,
  coalesce(legal.limitations,ARRAY['Escopo ainda não catalogado para a data consultada.'])
   AS limitations
 FROM scopes LEFT JOIN LATERAL (
  SELECT * FROM se_liga_brasil.office_legal_scope_version versions
  WHERE versions.office_kind=scopes.office_kind AND versions.jurisdiction=scopes.jurisdiction
   AND versions.reviewed_on<=%s
  ORDER BY versions.reviewed_on DESC,versions.catalog_version DESC LIMIT 1
 ) legal ON true ORDER BY scopes.office_kind,scopes.jurisdiction
"""


def fetch_public_office_scopes(connection, person_id, as_of):
    """One query across observed candidacies and mandates; neither proves current exercise."""
    canonical_person_id = str(UUID(str(person_id)))
    rows = connection.execute(
        PERSON_SCOPE_SQL,
        (canonical_person_id, canonical_person_id, as_of),
    ).fetchall()
    result = []
    for row in rows:
        public = dict(row)
        for field in ("reviewed_on", "legal_valid_from", "legal_valid_until"):
            value = public[field]
            public[field] = value.isoformat() if value else None
        public["temporal_status"] = "legal_validity_not_established"
        public["association_status"] = "observed_office_not_current_exercise"
        result.append(public)
    return result
