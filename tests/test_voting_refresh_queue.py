from datetime import date
from uuid import uuid4

import pytest

from database.voting_refresh import claim_voting_refresh, fail_voting_refresh, finish_voting_refresh


@pytest.mark.integration
def test_refresh_queue_is_idempotent_leased_and_processed(integration_database):
    connection = integration_database
    for expected in (90, 0):
        assert (
            connection.execute(
                "SELECT se_liga_brasil.enqueue_voting_refresh(%s) AS total", (date(2026, 10, 1),)
            ).fetchone()["total"]
            == expected
        )
    connection.execute(
        "DELETE FROM se_liga_brasil.voting_refresh_job WHERE starts_on<DATE '2026-09-30'"
    )
    worker, stranger = uuid4(), uuid4()
    job = claim_voting_refresh(connection, worker)
    assert job["starts_on"] == date(2026, 9, 30)
    assert job["ends_on"] == date(2026, 9, 30)
    with pytest.raises(ValueError, match="lease"):
        finish_voting_refresh(connection, job["id"], stranger, {})
    finish_voting_refresh(connection, job["id"], worker, {"rows": 2, "coverage": "partial"})
    next_job = claim_voting_refresh(connection, stranger)
    assert next_job["id"] != job["id"]
    fail_voting_refresh(connection, next_job["id"], stranger, "SOURCE_COOLDOWN", 3600)
    assert claim_voting_refresh(connection, worker) is None
    rows = connection.execute(
        "SELECT status,processed FROM se_liga_brasil.voting_refresh_job ORDER BY status"
    ).fetchall()
    assert rows == [
        {"status": "failed", "processed": False},
        {"status": "processed", "processed": True},
    ]
