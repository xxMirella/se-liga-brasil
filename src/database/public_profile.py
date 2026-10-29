"""Private PostgreSQL adapter exposing whitelisted canonical public facts only."""

from contextlib import contextmanager

from psycopg.pq import TransactionStatus


class PublicProfileRepository:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def read_snapshot(self):
        """One consistent read-only transaction; nested calls join the open one.

        Joining avoids repeating BEGIN/SET/COMMIT round trips and keeps every fact of a
        composed response in the same PostgreSQL snapshot.
        """
        if self.connection_has_open_transaction():
            yield
            return
        with self.connection.transaction():
            # No parameters: both settings travel in a single round trip.
            self.connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY; "
                "SET LOCAL statement_timeout='5s'"
            )
            yield

    def connection_has_open_transaction(self):
        information = getattr(self.connection, "info", None)
        return information is not None and information.transaction_status != TransactionStatus.IDLE

    def fetch_person(self, person_id):
        return self.connection.execute(
            "SELECT id::text AS person_id,display_name FROM se_liga_brasil.person "
            "WHERE id=%s::uuid",
            (person_id,),
        ).fetchone()

    def fetch_exercises(self, query):
        return self.connection.execute(
            """SELECT e.id AS exercise_id,t.id AS term_id,t.office_kind,t.represented_uf,
               i.code AS institution_code,i.name AS institution_name,
               e.starts_on,e.ends_before,e.capacity
            FROM se_liga_brasil.office_exercise e
            JOIN se_liga_brasil.office_term t ON t.id=e.term_id
            JOIN se_liga_brasil.institution i ON i.id=t.institution_id
            WHERE t.person_id=%s::uuid AND e.starts_on<=%s
              AND (e.ends_before IS NULL OR e.ends_before>%s)
              AND (%s::text IS NULL OR t.office_kind=%s)
              AND (%s::bigint IS NULL OR e.id=%s)
            ORDER BY e.starts_on DESC,e.id DESC LIMIT 101""",
            (
                query.person_id,
                query.end_on,
                query.start_on,
                query.office_kind,
                query.office_kind,
                query.exercise_id,
                query.exercise_id,
            ),
        ).fetchall()

    def fetch_votes(self, query, cursor):
        cursor_date, cursor_id = cursor if cursor else (None, None)
        return self.connection.execute(
            """SELECT v.id AS voting_id,v.held_on,v.held_at,v.date_precision,
              v.subject,v.subject_kind,v.method,v.result AS collective_result,
              v.stage,v.round_number,v.legislative_body_code,v.nominal_availability,
              pv.choice,pv.participation_status,i.code AS institution_code,
              i.name AS institution_name,p.id AS proposition_id,p.kind AS proposition_kind,
              p.number AS proposition_number,p.year AS proposition_year,p.title AS proposition_title
            FROM se_liga_brasil.person_vote pv
            JOIN se_liga_brasil.voting v ON v.id=pv.voting_id
            JOIN se_liga_brasil.proposition p ON p.id=v.proposition_id
            JOIN se_liga_brasil.institution i ON i.id=v.institution_id
            WHERE pv.person_id=%s::uuid AND v.held_on BETWEEN %s AND %s
              AND (%s::date IS NULL OR (v.held_on,v.id)<(%s::date,%s::bigint))
              AND ((%s::text IS NULL AND %s::bigint IS NULL) OR EXISTS (
                SELECT 1 FROM se_liga_brasil.office_exercise e
                JOIN se_liga_brasil.office_term t ON t.id=e.term_id
                WHERE t.person_id=pv.person_id AND t.institution_id=v.institution_id
                  AND e.starts_on<=v.held_on AND (e.ends_before IS NULL OR e.ends_before>v.held_on)
                  AND (%s::text IS NULL OR t.office_kind=%s)
                  AND (%s::bigint IS NULL OR e.id=%s)))
            ORDER BY v.held_on DESC,v.id DESC LIMIT %s""",
            (
                query.person_id,
                query.start_on,
                query.end_on,
                cursor_date,
                cursor_date,
                cursor_id,
                query.office_kind,
                query.exercise_id,
                query.office_kind,
                query.office_kind,
                query.exercise_id,
                query.exercise_id,
                query.limit + 1,
            ),
        ).fetchall()

    def fetch_vote_coverage(self, query):
        available = self.connection.execute(
            "SELECT to_regclass('se_liga_brasil.person_career_coverage_receipt') "
            "IS NOT NULL AS available"
        ).fetchone()["available"]
        if not available:
            return []
        return self.connection.execute(
            """SELECT institution,source,partition_key,domain,
              starts_on,ends_before,checked_on,acquisition_status,
              identity_verified,enumeration_complete,source_period_complete,
              artifact_verified,scope_verified
            FROM se_liga_brasil.person_career_coverage_receipt
            WHERE person_id=%s::uuid AND domain='votes' AND starts_on<=%s AND ends_before>%s
            ORDER BY institution,starts_on,ends_before LIMIT 201""",
            (query.person_id, query.end_on, query.start_on),
        ).fetchall()
