"""Explicit cron setup, bounded collection and a queue-consuming Python worker."""

import time
from contextlib import ExitStack
from datetime import date
from uuid import uuid4

import httpx

from database.operations import PROJECT_ROOT, connect_database
from database.voting_refresh import (
    claim_voting_refresh,
    configure_voting_schedule,
    fail_voting_refresh,
    finish_voting_refresh,
)
from service.dataset_storage.supabase import SupabaseDatasetStorage, load_storage_configuration
from service.observability.reporting import describe_error
from service.voting_pipeline.runner import run_source_refresh


def execute_voting_command(arguments):
    if arguments.command == "configure-voting-schedule":
        with connect_database(arguments.env_file) as connection:
            return configure_voting_schedule(connection)
    with ExitStack() as stack:
        connection = stack.enter_context(connect_database(arguments.env_file))
        publisher = None
        if not arguments.local_only:
            configuration = load_storage_configuration(arguments.env_file)
            client = stack.enter_context(httpx.Client(timeout=60, follow_redirects=False))
            publisher = SupabaseDatasetStorage(configuration, client)
        if arguments.command == "voting-worker":
            return run_voting_worker(connection, arguments, publisher)
        if not arguments.start_date or not arguments.end_date:
            raise ValueError("Explicit voting dates are required")
        return run_requested_refresh(
            connection,
            arguments,
            publisher,
            arguments.source,
            date.fromisoformat(arguments.start_date),
            date.fromisoformat(arguments.end_date),
        )


def run_requested_refresh(connection, arguments, publisher, source, start, end):
    return run_source_refresh(
        connection,
        arguments.storage_directory or PROJECT_ROOT / "data/enrichment",
        arguments.dataset_directory or PROJECT_ROOT / "data/derived",
        source,
        start,
        end,
        publisher=publisher,
        limit=arguments.limit,
        max_identity_profiles=arguments.max_identity_profiles,
        proposition_ids=tuple(
            filter(None, (getattr(arguments, "proposition_ids", None) or "").split(","))
        ),
        **({"cached_only": True} if getattr(arguments, "cached_only", False) else {}),
    )


def run_voting_worker(connection, arguments, publisher):
    if not 1 <= arguments.max_jobs <= 100 or not 5 <= arguments.poll_seconds <= 60:
        raise ValueError("Invalid worker budget or polling interval")
    if arguments.local_only:
        raise ValueError("The durable worker requires publication to Storage")
    worker_id, results = uuid4(), []
    while True:
        completed = process_voting_jobs(connection, arguments, publisher, worker_id)
        results.extend(completed)
        if not arguments.daemon:
            return {"processed": len(results), "jobs": results}
        results.clear()
        time.sleep(arguments.poll_seconds)


def process_voting_jobs(connection, arguments, publisher, worker_id):
    results = []
    for _ in range(arguments.max_jobs):
        job = claim_voting_refresh(connection, worker_id)
        if job is None:
            break
        try:
            summary = run_requested_refresh(
                connection, arguments, publisher, job["source"], job["starts_on"], job["ends_on"]
            )
            if not summary.get("discovery_complete", True):
                raise ValueError("VOTING_DISCOVERY_BUDGET_EXCEEDED")
            finish_voting_refresh(connection, job["id"], worker_id, summary)
            results.append(summary)
        except Exception as error:
            failure = describe_error(error)
            fail_voting_refresh(
                connection,
                job["id"],
                worker_id,
                failure.get("code", "FAILED"),
                failure.get("retry_after_seconds", 3600),
            )
            results.append(
                {"source": job["source"], "status": "failed", "code": failure.get("code", "FAILED")}
            )
    return results
