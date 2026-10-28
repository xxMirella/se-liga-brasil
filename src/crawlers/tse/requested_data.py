"""Personal-evidence scope and set-based repairs from already ingested TSE facts."""

from dataclasses import dataclass

from crawlers.tse.enrichment import AssetBackfillConfiguration


@dataclass(frozen=True)
class RequestedTseConfiguration(AssetBackfillConfiguration):
    document_fingerprints: frozenset[str] = frozenset()
    name_birth_pairs: frozenset[tuple[str, str]] = frozenset()
    documentless_name_birth_pairs: frozenset[tuple[str, str]] = frozenset()
    conflicting_document_fingerprints: frozenset[str] = frozenset()

    def allows_identity(self, record):
        evidence = record.get("identityEvidence", {})
        fingerprint = evidence.get("documentFingerprint")
        if fingerprint in self.conflicting_document_fingerprints:
            return False
        pair = (evidence.get("normalizedName"), record["normalizedData"].get("birthDate"))
        if fingerprint:
            return (fingerprint in self.document_fingerprints
                    or pair in self.documentless_name_birth_pairs)
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
    foreign_documents = connection.execute(
        """SELECT document_fingerprint FROM se_liga_brasil.person_document_identity
        WHERE NOT(person_id=ANY(%s::uuid[]))""", (person_ids,),
    ).fetchall()
    return {
        "conflicting_document_fingerprints": frozenset(
            row["document_fingerprint"] for row in foreign_documents
        ),
        "document_fingerprints": frozenset(
            row["document_fingerprint"] for row in rows if row["document_fingerprint"]
        ),
        "name_birth_pairs": frozenset(
            (row["normalized_name"], row["birth_date"])
            for row in rows
            if row["unique_name_birth"] and row["birth_date"]
        ),
        "documentless_name_birth_pairs": frozenset(
            (row["normalized_name"], row["birth_date"])
            for row in rows
            if row["unique_name_birth"] and row["birth_date"]
            and not row["document_fingerprint"]
        ),
    }


def load_requested_election_scope(connection, person_ids):
    """Mandate start selects an election archive, never establishes candidacy."""
    return connection.execute(
        """SELECT p.id::text person_id,
          coalesce(c.election_year,extract(year FROM t.term_start)::int-1) election_year,
          coalesce(c.represented_uf,t.represented_uf) represented_uf
        FROM se_liga_brasil.person p
        LEFT JOIN LATERAL(SELECT election_year,represented_uf
          FROM se_liga_brasil.electoral_candidacy c WHERE c.person_id=p.id
          ORDER BY election_year DESC LIMIT 1) c ON true
        LEFT JOIN LATERAL(SELECT term_start,represented_uf
          FROM se_liga_brasil.office_term t
          JOIN se_liga_brasil.institution i ON i.id=t.institution_id AND i.code='senado'
          JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
          WHERE t.person_id=p.id AND e.ends_before IS NULL AND t.term_start IS NOT NULL
          ORDER BY t.term_start DESC LIMIT 1) t ON true
        WHERE p.id=ANY(%s::uuid[])""", (person_ids,),
    ).fetchall()


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
