"""Delete fulfilled work items, retaining unresolved work and collected facts."""


def purge_processed_gaps(connection, batch_size=1000, max_batches=10) -> dict:
    if not 1 <= batch_size <= 5000 or not 1 <= max_batches <= 100:
        raise ValueError("Cleanup limits must be bounded")
    deleted = 0
    for _ in range(max_batches):
        with connection.transaction():
            row = connection.execute(
                """
                WITH selected AS (
                  SELECT id FROM se_liga_brasil.person_data_gap
                  WHERE is_processed AND status='resolved' AND claimed_by IS NULL
                  ORDER BY id FOR UPDATE SKIP LOCKED LIMIT %s
                ), removed AS (
                  DELETE FROM se_liga_brasil.person_data_gap g USING selected s
                  WHERE g.id=s.id RETURNING g.id
                ) SELECT count(*) AS total FROM removed
            """,
                (batch_size,),
            ).fetchone()
        deleted += row["total"]
        if row["total"] < batch_size:
            break
    return {"deleted_processed_gaps": deleted, "batch_size": batch_size}
