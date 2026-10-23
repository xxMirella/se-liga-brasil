"""Reuse durable source/month jobs across repeated historical requests."""

from psycopg.types.json import Jsonb


def enqueue_missing_voting_partitions(connection, source, partitions, requested_on, maximum):
    if source not in {"senado", "camara"} or not 1 <= maximum <= 100:
        raise ValueError("Invalid voting backfill source or budget")
    lock_key = "se_liga_brasil:voting-backfill:" + source
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_key,))
        rows = connection.execute(
            """INSERT INTO se_liga_brasil.voting_refresh_job
              (source,requested_on,starts_on,ends_on,summary)
            SELECT %s,%s,p.starts_on,p.ends_on,
              '{"historical_backfill":true}'::jsonb
            FROM jsonb_to_recordset(%s) p(starts_on date,ends_on date)
            WHERE NOT EXISTS (
              SELECT 1 FROM se_liga_brasil.voting_refresh_job j
              WHERE j.source=%s AND j.starts_on=p.starts_on AND j.ends_on=p.ends_on)
            ORDER BY p.starts_on LIMIT %s
            ON CONFLICT(source,requested_on,starts_on) DO NOTHING RETURNING starts_on,ends_on""",
            (
                source,
                requested_on,
                Jsonb(
                    [
                        {"starts_on": lower.isoformat(), "ends_on": upper.isoformat()}
                        for lower, upper in partitions
                    ]
                ),
                source,
                maximum,
            ),
        ).fetchall()
    return [
        {"starts_on": row["starts_on"].isoformat(), "ends_on": row["ends_on"].isoformat()}
        for row in rows
    ]
