"""Personal-evidence scope and set-based repairs from already ingested TSE facts."""

from dataclasses import dataclass

from crawlers.tse.enrichment import AssetBackfillConfiguration


@dataclass(frozen=True)
class RequestedTseConfiguration(AssetBackfillConfiguration):
    document_fingerprints: frozenset[str] = frozenset()
    name_birth_pairs: frozenset[tuple[str, str]] = frozenset()

    def allows_identity(self, record):
        evidence = record.get("identityEvidence", {})
        fingerprint = evidence.get("documentFingerprint")
        if fingerprint:
            return fingerprint in self.document_fingerprints
        pair = (evidence.get("normalizedName"), record["normalizedData"].get("birthDate"))
        return pair in self.name_birth_pairs


def load_requested_personal_scope(connection, person_ids):
    rows = connection.execute(
        """
        SELECT p.normalized_name,p.birth_date::text,d.document_fingerprint,
          (SELECT count(*) FROM se_liga_brasil.person peer
           WHERE peer.normalized_name=p.normalized_name AND peer.birth_date=p.birth_date)=1
          AS unique_name_birth
        FROM se_liga_brasil.person p
        LEFT JOIN se_liga_brasil.person_document_identity d ON d.person_id=p.id
        WHERE p.id=ANY(%s::uuid[])
        """,
        (person_ids,),
    ).fetchall()
    return {
        "document_fingerprints": frozenset(
            row["document_fingerprint"] for row in rows if row["document_fingerprint"]
        ),
        "name_birth_pairs": frozenset(
            (row["normalized_name"], row["birth_date"])
            for row in rows
            if row["unique_name_birth"] and row["birth_date"]
        ),
    }


def repair_missing_personal_fields(connection, person_ids):
    return connection.execute(
        """
        WITH evidence AS (
          SELECT f.person_id,
            (array_agg(f.normalized_value->>'birthDate') FILTER
              (WHERE f.normalized_value->>'birthDate' IS NOT NULL))[1] AS birth_date,
            (array_agg(f.normalized_value->>'educationLevel' ORDER BY r.effective_at DESC)
              FILTER (WHERE f.normalized_value->>'educationLevel' IS NOT NULL))[1] AS education,
            count(DISTINCT f.normalized_value->>'birthDate') AS birth_variants
          FROM se_liga_brasil.person_fact f
          JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
          JOIN se_liga_brasil.source s ON s.id=r.source_id AND s.code='tse'
          WHERE f.person_id=ANY(%s::uuid[]) AND f.field_name LIKE 'tse:candidate:%%'
          GROUP BY f.person_id
        )
        UPDATE se_liga_brasil.person p SET
          birth_date=coalesce(p.birth_date,
            CASE WHEN e.birth_variants=1 THEN e.birth_date::date END),
          education_level=coalesce(p.education_level,e.education),updated_at=now()
        FROM evidence e WHERE p.id=e.person_id
          AND ((p.birth_date IS NULL AND e.birth_variants=1)
            OR (p.education_level IS NULL AND e.education IS NOT NULL))
        RETURNING p.id::text AS person_id
        """,
        (person_ids,),
    ).fetchall()
