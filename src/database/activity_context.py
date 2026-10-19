"""Parametrized relational validation of ownership and proven membership periods."""

from dataclasses import asdict

from service.ingestion.contracts import IngestionError


class PostgresActivityContextRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def link_context(self, context) -> int:
        row = self.connection.execute(
            """
            INSERT INTO se_liga_brasil.person_activity_context(source_id,activity_kind,
            external_key,person_id,role,political_party_id,political_party_affiliation_id,
            office_term_id,context_kind,occurred_at,observed_at,source_record_id)
            SELECT %(source_id)s,%(activity_kind)s,%(external_key)s,person.id,%(role)s,
            affiliation.political_party_id,affiliation.id,office.id,
            CASE WHEN affiliation.evidence_kind='electoral_declaration'
             THEN 'electoral_declaration' ELSE 'administrative' END,
            %(occurred_at)s,%(observed_at)s,%(source_record_id)s
            FROM se_liga_brasil.person person
            JOIN se_liga_brasil.source_record record ON record.id=%(source_record_id)s
             AND record.source_id=%(source_id)s
            LEFT JOIN se_liga_brasil.political_party_affiliation affiliation
             ON affiliation.id=%(political_party_affiliation_id)s
             AND affiliation.person_id=person.id
            LEFT JOIN se_liga_brasil.office_term office ON office.id=%(office_term_id)s
             AND office.person_id=person.id
            WHERE person.id=se_liga_brasil.canonical_person_id(%(person_id)s::uuid)
             AND (%(political_party_affiliation_id)s IS NULL OR affiliation.id IS NOT NULL)
             AND (%(office_term_id)s IS NULL OR office.id IS NOT NULL)
             AND (%(occurred_at)s::timestamptz IS NULL OR office.id IS NULL OR EXISTS(
              SELECT 1 FROM se_liga_brasil.office_exercise exercise WHERE exercise.term_id=office.id
              AND %(occurred_at)s::date>=exercise.starts_on
              AND (exercise.ends_before IS NULL OR %(occurred_at)s::date<exercise.ends_before)))
             AND (%(occurred_at)s::timestamptz IS NULL OR affiliation.id IS NULL
              OR (affiliation.evidence_kind<>'electoral_declaration'
               AND affiliation.valid_from IS NOT NULL
               AND %(occurred_at)s::date>=affiliation.valid_from
               AND (affiliation.valid_until IS NULL
                OR %(occurred_at)s::date<affiliation.valid_until)))
            ON CONFLICT(source_id,activity_kind,external_key,person_id,role,source_record_id)
            DO UPDATE SET observed_at=excluded.observed_at
            RETURNING id
            """,
            asdict(context),
        ).fetchone()
        if not row:
            raise IngestionError("ACTIVITY_CONTEXT_NOT_VERIFIED")
        return row["id"]
