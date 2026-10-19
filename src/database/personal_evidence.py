"""Source-independent, read-only matching of full legal name and exact birth date."""

from psycopg.types.json import Jsonb


def lookup_unique_people_by_name_birth(connection, evidence):
    if not evidence:
        return {}
    requested = [
        {"normalized_name": item["normalized_name"], "birth_date": item["birth_date"]}
        for item in evidence
    ]
    rows = connection.execute(
        """
        WITH requested AS (
          SELECT DISTINCT normalized_name,birth_date
          FROM jsonb_to_recordset(%s::jsonb) q(normalized_name text,birth_date date)
        )
        SELECT q.normalized_name,q.birth_date::text,array_agg(p.id::text) AS person_ids
        FROM requested q JOIN se_liga_brasil.person p
          ON p.normalized_name=q.normalized_name AND p.birth_date=q.birth_date
        WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
          WHERE a.alias_person_id=p.id)
        GROUP BY q.normalized_name,q.birth_date
    """,
        (Jsonb(requested),),
    ).fetchall()
    return {
        (row["normalized_name"], row["birth_date"]): row["person_ids"][0]
        for row in rows
        if len(row["person_ids"]) == 1
    }


def lookup_unique_people_by_document(connection, evidence):
    requested = [
        {"fingerprint": item["document_fingerprint"], "birth_date": item["birth_date"]}
        for item in evidence
        if item.get("document_fingerprint")
    ]
    if not requested:
        return {}
    rows = connection.execute(
        """WITH requested AS (
          SELECT DISTINCT fingerprint,birth_date FROM jsonb_to_recordset(%s::jsonb)
            q(fingerprint text,birth_date date)
        )
        SELECT q.fingerprint,array_agg(DISTINCT p.id::text) AS person_ids
        FROM requested q JOIN se_liga_brasil.person_document_identity d
          ON d.document_kind='cpf' AND d.document_fingerprint=q.fingerprint
        JOIN se_liga_brasil.person p ON p.id=d.person_id AND p.birth_date=q.birth_date
        WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
          WHERE a.alias_person_id=p.id)
        GROUP BY q.fingerprint""",
        (Jsonb(requested),),
    ).fetchall()
    return {row["fingerprint"]: row["person_ids"][0] for row in rows if len(row["person_ids"]) == 1}
