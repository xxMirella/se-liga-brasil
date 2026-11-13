"""Durable gap assessment, bounded worker leases and source-wide cooldowns."""

from itertools import batched
from uuid import uuid4

from psycopg.types.json import Jsonb

from database.operations import read_sql_file
from service.completeness.rules import SATISFIED_STATES
from service.ingestion.contracts import IngestionError


def stage_current_gaps(connection, report) -> int:
    """Load the gaps visible in this assessment into a transaction-local staging table."""
    missing = (
        {"person_id": row["person_id"], "field_name": field, "quality_state": status}
        for row in report["people"]
        for field, status in row["fields"].items()
        if status not in SATISFIED_STATES
    )
    connection.execute(
        "CREATE TEMP TABLE IF NOT EXISTS person_data_gap_assessment("
        "person_id uuid NOT NULL,field_name text NOT NULL,quality_state text NOT NULL,"
        "PRIMARY KEY(person_id,field_name))"
    )
    connection.execute("TRUNCATE person_data_gap_assessment")
    count = 0
    for batch in batched(missing, 1000):
        connection.execute(
            """
            INSERT INTO person_data_gap_assessment(person_id,field_name,quality_state)
            SELECT (item->>'person_id')::uuid,item->>'field_name',item->>'quality_state'
            FROM jsonb_array_elements(%s) item
            ON CONFLICT(person_id,field_name) DO UPDATE SET quality_state=excluded.quality_state
            """,
            (Jsonb(batch),),
        )
        count += len(batch)
    return count


def upsert_changed_gaps(connection, assessment_id) -> None:
    """Insert new gaps and rewrite existing ones only when the state or lifecycle changed."""
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person_data_gap AS current(
          person_id,field_name,quality_state,last_assessment_id)
        SELECT person_id,field_name,quality_state,%s::uuid FROM person_data_gap_assessment
        ON CONFLICT(person_id,field_name) DO UPDATE SET
          quality_state=excluded.quality_state,last_checked_at=now(),
          last_assessment_id=excluded.last_assessment_id,
          status=CASE WHEN current.status='resolved' THEN 'queued' ELSE current.status END,
          next_attempt_at=CASE WHEN current.status='resolved'
            THEN now() ELSE current.next_attempt_at END,
          resolved_at=NULL,is_processed=false,processed_at=NULL
        WHERE current.quality_state IS DISTINCT FROM excluded.quality_state
          OR current.status='resolved' OR current.is_processed
        """,
        (assessment_id,),
    )


def resolve_absent_gaps(connection, assessment_id, people) -> None:
    """Resolve open gaps of assessed people that are absent from the current assessment."""
    connection.execute(
        """
        UPDATE se_liga_brasil.person_data_gap AS gap SET status='resolved',
          quality_state='resolved',resolved_at=now(),is_processed=true,processed_at=now(),
          last_checked_at=now(),last_assessment_id=%s::uuid,claimed_by=NULL,lease_until=NULL
        WHERE gap.person_id=ANY(%s::uuid[]) AND gap.status<>'resolved'
          AND NOT EXISTS(
            SELECT 1 FROM person_data_gap_assessment present
            WHERE present.person_id=gap.person_id AND present.field_name=gap.field_name)
        """,
        (assessment_id, people),
    )


def persist_data_gaps(connection, report) -> dict:
    assessment_id = str(uuid4())
    people = [row["person_id"] for row in report["people"]]
    with connection.transaction():
        count = stage_current_gaps(connection, report)
        upsert_changed_gaps(connection, assessment_id)
        resolve_absent_gaps(connection, assessment_id, people)
    return {"assessment_id": assessment_id, "open_fields_assessed": count}


def route_data_gaps(connection) -> None:
    connection.execute(read_sql_file("queries/route_data_gaps.sql"))


def claim_data_gaps(
    connection, worker_id, person_id=None, limit=1000, field_names=None, source_codes=None
) -> list:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise IngestionError("INVALID_DATA_GAP_LIMIT")
    with connection.transaction():
        return connection.execute(
            read_sql_file("queries/claim_data_gaps.sql"),
            (
                person_id,
                person_id,
                field_names,
                field_names,
                source_codes,
                source_codes,
                limit,
                worker_id,
            ),
        ).fetchall()


def release_data_gaps(connection, worker_id, *, delay_seconds=86400, error_code=None) -> None:
    connection.execute(
        """
        UPDATE se_liga_brasil.person_data_gap SET status='queued',claimed_by=NULL,lease_until=NULL,
          next_attempt_at=greatest(next_attempt_at,now()+%s*interval '1 second'),
          last_error_code=coalesce(%s,last_error_code)
        WHERE claimed_by=%s::uuid AND status='running'
    """,
        (delay_seconds, error_code, worker_id),
    )


def postpone_source(connection, source, delay_seconds, error_code, http_status=None) -> None:
    with connection.transaction():
        connection.execute(
            """
            INSERT INTO se_liga_brasil.source_request_policy AS current(
              source_code,cooldown_until,last_error_code,last_http_status)
            VALUES(%s,now()+%s*interval '1 second',%s,%s)
            ON CONFLICT(source_code) DO UPDATE SET
              cooldown_until=greatest(current.cooldown_until,excluded.cooldown_until),
              last_error_code=excluded.last_error_code,last_http_status=excluded.last_http_status,
              updated_at=now()
        """,
            (source, delay_seconds, error_code, http_status),
        )
        connection.execute(
            """
            UPDATE se_liga_brasil.person_data_gap SET
              next_attempt_at=greatest(next_attempt_at,now()+%s*interval '1 second'),
              last_error_code=%s
            WHERE assigned_source=%s AND status IN ('queued','running')
              AND (next_attempt_at<now()+%s*interval '1 second'
                OR last_error_code IS DISTINCT FROM %s)
        """,
            (delay_seconds, error_code, source, delay_seconds, error_code),
        )


def block_data_gaps(connection, worker_id, source, fields, error_code):
    connection.execute(
        """
        UPDATE se_liga_brasil.person_data_gap SET status='blocked',claimed_by=NULL,
          lease_until=NULL,last_error_code=%s
        WHERE claimed_by=%s::uuid AND assigned_source=%s AND field_name=ANY(%s)
          AND status='running'
        """,
        (error_code, worker_id, source, list(fields)),
    )


def defer_unmatched_institutional_people(connection, worker_id, source, person_ids):
    if not person_ids:
        return
    connection.execute(
        """
        UPDATE se_liga_brasil.person_data_gap SET
          assigned_source=CASE WHEN field_name='current_political_party'
            THEN 'tse_filiation' ELSE assigned_source END,
          status=CASE WHEN field_name='current_political_party' THEN 'queued' ELSE 'blocked' END,
          claimed_by=NULL,lease_until=NULL,next_attempt_at=now(),
          last_error_code='INSTITUTIONAL_IDENTITY_OR_CURRENT_ROLE_NOT_CONFIRMED'
        WHERE claimed_by=%s::uuid AND assigned_source=%s AND person_id=ANY(%s::uuid[])
          AND status='running'
        """,
        (worker_id, source, list(person_ids)),
    )
