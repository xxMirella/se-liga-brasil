from datetime import date

import pytest

from service.voting_pipeline.backfill import historical_voting_partitions


def test_history_since_2000_only_plans_verified_senate_exercise():
    exercises = [
        {"institution": "senado", "starts_on": date(2019, 2, 1), "ends_before": None},
        {"institution": "alerj", "starts_on": date(2003, 2, 1), "ends_before": date(2019, 2, 1)},
    ]
    actual = historical_voting_partitions(exercises, "senado", date(2000, 1, 1), date(2019, 3, 15))
    assert actual == [(date(2019, 2, 1), date(2019, 2, 28)), (date(2019, 3, 1), date(2019, 3, 15))]


def test_closed_exercise_and_duplicate_evidence_do_not_extend_or_duplicate_jobs():
    exercise = {
        "institution": "camara",
        "starts_on": date(2001, 2, 10),
        "ends_before": date(2001, 3, 2),
    }
    assert historical_voting_partitions(
        [exercise, exercise], "camara", date(2000, 1, 1), date(2026, 10, 22)
    ) == [(date(2001, 2, 10), date(2001, 2, 28)), (date(2001, 3, 1), date(2001, 3, 1))]
    assert historical_voting_partitions([], "senado", date(2000, 1, 1), date(2026, 10, 22)) == []


@pytest.mark.integration
def test_historical_jobs_reuse_checkpoints_across_request_dates(integration_database):
    from database.voting_backfill import enqueue_missing_voting_partitions

    c = integration_database
    periods = [(date(2019, 2, 1), date(2019, 2, 28)), (date(2019, 3, 1), date(2019, 3, 31))]
    first = enqueue_missing_voting_partitions(c, "senado", periods, date(2026, 10, 21), 1)
    assert len(first) == 1
    second = enqueue_missing_voting_partitions(c, "senado", periods, date(2026, 10, 22), 10)
    assert len(second) == 1
    assert enqueue_missing_voting_partitions(c, "senado", periods, date(2026, 10, 23), 10) == []


@pytest.mark.integration
def test_source_cooldown_preserves_attempt_budget_and_other_source_remains_available(
    integration_database,
):
    from uuid import uuid4

    from database.voting_backfill import enqueue_missing_voting_partitions
    from database.voting_refresh import claim_voting_refresh

    c = integration_database
    periods = [(date(2019, 2, 1), date(2019, 2, 28))]
    for source in ("camara", "senado"):
        enqueue_missing_voting_partitions(c, source, periods, date(2026, 10, 22), 1)
    c.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES ('camara','Test chamber','https://example.test','api')"
    )
    c.execute("""INSERT INTO se_liga_brasil.source_request_policy
      (source_code,cooldown_until) VALUES ('camara',now()+interval '1 hour')
      ON CONFLICT(source_code) DO UPDATE SET cooldown_until=excluded.cooldown_until""")
    assert claim_voting_refresh(c, uuid4(), source="camara") is None
    job = claim_voting_refresh(c, uuid4())
    assert job["source"] == "senado"
    assert (
        c.execute(
            "SELECT attempts FROM se_liga_brasil.voting_refresh_job WHERE source='camara'"
        ).fetchone()["attempts"]
        == 0
    )


@pytest.mark.integration
def test_cleanup_keeps_only_strict_boolean_historical_checkpoints(integration_database):
    from uuid import uuid4

    from psycopg.types.json import Jsonb

    from database.voting_backfill import enqueue_missing_voting_partitions
    from database.voting_refresh import (
        VOTING_JOB_CLEANUP_SQL,
        claim_voting_refresh,
        finish_voting_refresh,
    )

    c = integration_database
    enqueue_missing_voting_partitions(
        c, "senado", [(date(2019, 2, 1), date(2019, 2, 28))], date(2026, 10, 22), 1
    )
    worker = uuid4()
    job = claim_voting_refresh(c, worker)
    finish_voting_refresh(c, job["id"], worker, {"rows": 1, "historical_backfill": False})
    for month, marker in [(3, {}), (4, {"historical_backfill": "true"})]:
        c.execute(
            """INSERT INTO se_liga_brasil.voting_refresh_job
          (source,requested_on,starts_on,ends_on,status,processed,processed_at,summary)
          VALUES ('senado',DATE '2026-10-22',%s,%s,'processed',true,now()-interval '8 days',%s)""",
            (date(2019, month, 1), date(2019, month, 28), Jsonb(marker)),
        )
    c.execute("UPDATE se_liga_brasil.voting_refresh_job SET processed_at=now()-interval '8 days'")
    c.execute(VOTING_JOB_CLEANUP_SQL)
    rows = c.execute("SELECT starts_on,summary FROM se_liga_brasil.voting_refresh_job").fetchall()
    assert rows == [
        {"starts_on": date(2019, 2, 1), "summary": {"historical_backfill": True, "rows": 1}}
    ]
