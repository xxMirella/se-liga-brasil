"""Small private work queue; voting facts remain in partitioned files."""

from database.operations import read_sql_file, strip_transaction_wrapper

VOTING_JOB_CLEANUP_SQL = (
    "DELETE FROM se_liga_brasil.voting_refresh_job WHERE processed "
    "AND processed_at<now()-interval '7 days' "
    "AND summary->'historical_backfill' IS DISTINCT FROM 'true'::jsonb"
)


def apply_voting_refresh_schema(connection):
    installed = connection.execute(
        "SELECT to_regclass('se_liga_brasil.voting_refresh_job') IS NOT NULL AS installed"
    ).fetchone()["installed"]
    if not installed:
        with connection.transaction():
            connection.execute(
                strip_transaction_wrapper(read_sql_file("migrations/0019_voting_refresh_queue.sql"))
            )
    return not installed


def configure_voting_schedule(connection):
    apply_voting_refresh_schema(connection)
    with connection.transaction():
        connection.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")
        timezone = connection.execute(
            "SELECT current_setting('cron.timezone',true) AS timezone"
        ).fetchone()["timezone"]
        if timezone not in {None, "GMT", "UTC"}:
            raise ValueError("Cron timezone must be UTC/GMT for the configured schedule")
        row = connection.execute(
            "SELECT cron.schedule(%s,%s,%s) AS job_id",
            (
                "se-liga-brasil-voting-refresh",
                "0 11 1,15 * *",
                "SELECT se_liga_brasil.enqueue_voting_refresh();",
            ),
        ).fetchone()
        connection.execute(
            "SELECT cron.schedule(%s,%s,%s)",
            (
                "se-liga-brasil-voting-refresh-cleanup",
                "0 12 * * *",
                VOTING_JOB_CLEANUP_SQL + "; "
                "DELETE FROM cron.job_run_details WHERE jobid IN "
                "(SELECT jobid FROM cron.job WHERE jobname LIKE 'se-liga-brasil-voting-refresh%') "
                "AND end_time<now()-interval '7 days';",
            ),
        )
    return {"job_id": row["job_id"], "days": [1, 15], "local_time": "08:00 America/Belem"}


def claim_voting_refresh(connection, worker_id, source=None):
    return connection.execute(
        """WITH next AS (
          SELECT id FROM se_liga_brasil.voting_refresh_job candidate
          WHERE (%s::text IS NULL OR candidate.source=%s)
            AND NOT EXISTS (SELECT 1 FROM se_liga_brasil.source_request_policy policy
              WHERE policy.source_code=candidate.source AND policy.cooldown_until>now())
            AND NOT processed AND attempts<3 AND (retry_after IS NULL OR retry_after<=now())
            AND (status IN ('queued','failed') OR lease_until<now())
          ORDER BY created_at,starts_on DESC,source FOR UPDATE SKIP LOCKED LIMIT 1
        ) UPDATE se_liga_brasil.voting_refresh_job j SET status='running',
          attempts=attempts+1,claimed_by=%s::uuid,lease_until=now()+interval '60 minutes',
          error_code=NULL FROM next WHERE j.id=next.id
          RETURNING j.id::text,j.source,j.starts_on,j.ends_on,j.attempts""",
        (source, source, str(worker_id)),
    ).fetchone()


def finish_voting_refresh(connection, job_id, worker_id, summary):
    from psycopg.types.json import Jsonb

    result = connection.execute(
        """UPDATE se_liga_brasil.voting_refresh_job SET status='processed',processed=true,
          processed_at=now(),summary=summary || (%s::jsonb - 'historical_backfill'),
          claimed_by=NULL,lease_until=NULL
          WHERE id=%s::uuid AND claimed_by=%s::uuid AND status='running' AND lease_until>now()
          RETURNING id""",
        (Jsonb(summary), job_id, str(worker_id)),
    ).fetchone()
    if result is None:
        raise ValueError("Voting refresh lease is no longer owned")


def fail_voting_refresh(connection, job_id, worker_id, code, delay_seconds=3600):
    connection.execute(
        """UPDATE se_liga_brasil.voting_refresh_job SET status='failed',error_code=%s,
          claimed_by=NULL,lease_until=NULL,retry_after=now()+%s*interval '1 second'
          WHERE id=%s::uuid AND claimed_by=%s::uuid AND status='running'""",
        (str(code)[:100], max(60, min(int(delay_seconds), 86400)), job_id, str(worker_id)),
    )
