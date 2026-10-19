"""Shared source locks, cache transport and cooldown without SQL fact ingestion."""

from contextlib import contextmanager

import httpx

from database.data_gaps import postpone_source
from service.acquisition.http_client import OfficialHttpClient
from service.crawling.acquisition import local_run_lock
from service.ingestion.contracts import IngestionError
from service.legislative_collection.runtime import check_source_cooldown
from service.observability.reporting import describe_error


@contextmanager
def official_source_acquisition(connection, configuration, source, hosts, acquisition_factory):
    lock_key = f"se_liga_brasil:ingestion:{source.code}"
    acquired = connection.execute(
        "SELECT pg_try_advisory_lock(hashtext(%s)) AS acquired", (lock_key,)
    ).fetchone()["acquired"]
    if not acquired:
        raise IngestionError("CRAWLER_ALREADY_RUNNING_IN_DATABASE")
    try:
        check_source_cooldown(connection, source.code)
        with (
            local_run_lock(configuration.storage_directory / "source-locks" / source.code),
            httpx.Client(
                timeout=configuration.request_timeout_seconds,
                headers={"Accept": "application/json", "User-Agent": "SeLigaBrasilCrawler/1.0"},
            ) as client,
        ):
            transport = OfficialHttpClient(configuration, client, hosts)
            yield acquisition_factory(configuration, transport)
    except Exception as error:
        apply_collection_cooldown(connection, source.code, error)
        raise
    finally:
        connection.execute("SELECT pg_advisory_unlock(hashtext(%s))", (lock_key,))


def apply_collection_cooldown(connection, source_code, error):
    failure = describe_error(error)
    if failure.get("status") in {403, 429, 500, 502, 503, 504}:
        postpone_source(
            connection,
            source_code,
            max(3600, failure.get("retry_after_seconds", 0)),
            failure["code"],
            failure["status"],
        )
