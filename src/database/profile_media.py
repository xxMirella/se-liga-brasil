"""Bounded linked-profile reads and idempotent official photo writes."""

from psycopg.types.json import Jsonb


class ProfileMediaRepository:
    def __init__(self, connection):
        self.connection = connection

    def fetch_linked_profiles(self, limit):
        return self.connection.execute(
            """SELECT DISTINCT ON (f.person_id,s.code)
              f.person_id::text AS person_id,s.code AS source_code,f.source_record_id,
              f.normalized_value AS profile,r.source_url,p.photo_url
            FROM se_liga_brasil.person_fact f
            JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
            JOIN se_liga_brasil.source s ON s.id=r.source_id
            JOIN se_liga_brasil.person p ON p.id=f.person_id
            WHERE s.code IN ('camara','senado') AND f.review_status='verified'
              AND f.normalized_value->>'personId'=f.person_id::text
              AND f.normalized_value ? 'civilName' AND f.normalized_value ? 'birthDate'
              AND (f.field_name LIKE 'camara_profile:%%'
                OR f.field_name LIKE 'senado_profile:%%'
                OR f.field_name='current_public_office_observation')
              AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
                WHERE a.alias_person_id=p.id)
            ORDER BY f.person_id,s.code,r.fetched_at DESC,f.id DESC LIMIT %s""",
            (limit + 1,),
        ).fetchall()

    def save_official_photos(self, proposals):
        payload = Jsonb(
            [
                {
                    key: row[key]
                    for key in ("person_id", "source_record_id", "photo_url", "previous_photo_url")
                }
                for row in proposals
            ]
        )
        with self.connection.transaction():
            self.connection.execute("SET LOCAL statement_timeout='30s'")
            self.connection.execute(
                """INSERT INTO se_liga_brasil.person_fact(person_id,field_name,
                original_value,normalized_value,evidence_kind,review_status,source_record_id)
                SELECT person_id::uuid,'official_photo',jsonb_build_object('photoUrl',photo_url),
                  jsonb_build_object('photoUrl',photo_url),'administrative','verified',source_record_id
                FROM jsonb_to_recordset(%s::jsonb) AS photo(person_id text,
                  source_record_id bigint,photo_url text,previous_photo_url text)
                ON CONFLICT DO NOTHING""",
                (payload,),
            )
            row = self.connection.execute(
                """WITH updated AS (
                  UPDATE se_liga_brasil.person p SET photo_url=photo.photo_url
                  FROM jsonb_to_recordset(%s::jsonb) AS photo(person_id text,
                    source_record_id bigint,photo_url text,previous_photo_url text)
                  WHERE p.id=photo.person_id::uuid
                    AND p.photo_url IS NOT DISTINCT FROM photo.previous_photo_url RETURNING p.id
                ) SELECT count(*) AS updated FROM updated""",
                (payload,),
            ).fetchone()
        return row["updated"]

    def fetch_person_photo_coverage(self):
        return self.connection.execute(
            """SELECT count(*) AS total_people,
              count(*) FILTER (WHERE p.photo_url IS NOT NULL) AS people_with_photo_url,
              count(*) FILTER (WHERE p.photo_url IS NULL AND NOT EXISTS(
                SELECT 1 FROM se_liga_brasil.person_fact f
                JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
                JOIN se_liga_brasil.source s ON s.id=r.source_id
                WHERE f.person_id=p.id AND s.code IN ('camara','senado')
                  AND f.review_status='verified'
                  AND f.normalized_value->>'personId'=p.id::text
                  AND f.normalized_value ? 'civilName'
                  AND f.normalized_value ? 'birthDate'
              )) AS missing_photo_without_linked_institutional_profile
            FROM se_liga_brasil.person p WHERE NOT EXISTS(
              SELECT 1 FROM se_liga_brasil.person_identity_alias a WHERE a.alias_person_id=p.id)"""
        ).fetchone()
