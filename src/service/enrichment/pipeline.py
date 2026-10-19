"""Completeness plans collection; crawlers only acquire and normalize their sources."""

from uuid import uuid4

import httpx

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import (
    OFFICIAL_HOSTS,
    PARSER_VERSION,
    SOURCE,
    CrawlerConfiguration,
)
from crawlers.camara.pipeline import enrich_person
from crawlers.camara.projection import CamaraProjectionWriter
from service.acquisition.http_client import OfficialHttpClient
from service.enrichment.routing import index_current_members, select_member
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import describe_error, emit_event


def save_checked_coverage(repository, person_id) -> None:
    repository.connection.execute(
        """
        INSERT INTO se_liga_brasil.person_data_coverage(
          person_id,area,source_id,status,source_record_id)
        SELECT %s::uuid,area,%s,'partial',f.source_record_id
        FROM (VALUES('profile'),('offices'),('parties'),('propositions')) areas(area)
        CROSS JOIN LATERAL(SELECT source_record_id FROM se_liga_brasil.person_fact
          WHERE person_id=%s::uuid AND field_name LIKE 'camara_profile:%%'
          ORDER BY source_record_id DESC LIMIT 1) f
        ON CONFLICT(person_id,area,source_id) DO UPDATE SET checked_at=now(),
          source_record_id=excluded.source_record_id,status=excluded.status
    """,
        (person_id, repository.source_id, person_id),
    )


def collect_enrichment_plan(repository, acquisition, candidates) -> dict:
    members = []
    for rows, _ in acquisition.pages("deputados?itens=100", "camara_roster"):
        members.extend(rows)
    indexed = index_current_members(members)
    results, failures, unmatched, deferred = [], [], 0, 0
    deferred_people = []
    unmatched_people = []
    for position, candidate in enumerate(candidates):
        if not should_collect_candidate(candidate):
            continue
        member = select_member(candidate, indexed)
        if member is None:
            unmatched += 1
            unmatched_people.append(candidate["person_id"])
            continue
        if len(results) + len(failures) >= acquisition.configuration.max_people:
            deferred += 1
            deferred_people.append(candidate["person_id"])
            continue
        try:
            result = enrich_person(acquisition, repository, candidate, member)
            save_checked_coverage(repository, candidate["person_id"])
            results.append(result)
            emit_event("person_enriched", **result)
        except Exception as error:
            failures.append({"person_id": candidate["person_id"], **describe_error(error)})
            emit_event("person_enrichment_failed", **failures[-1])
            if failures[-1].get("status") in {403, 429, 500, 502, 503, 504}:
                deferred_people.extend(row["person_id"] for row in candidates[position + 1 :])
                deferred = len(deferred_people)
                break
    return {
        "people": results,
        "failures": failures,
        "unmatched_federal_candidates": unmatched,
        "unmatched_person_ids": unmatched_people,
        "deferred": deferred,
        "deferred_person_ids": deferred_people,
    }


def run_camara_collection(connection, storage, candidates) -> dict:
    configuration = CrawlerConfiguration(storage.resolve())
    repository = IngestionRepository(
        connection,
        SOURCE,
        CamaraProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "orchestrated_personal_enrichment"})
    try:
        with httpx.Client(
            timeout=configuration.request_timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "SeLigaBrasilCrawler/1.0"},
        ) as client:
            acquisition = CamaraAcquisition(
                configuration, OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
            )
            result = collect_enrichment_plan(repository, acquisition, candidates)
        repository.finish_run("partial" if result["failures"] else "completed", result)
        return result
    except BaseException:
        repository.finish_run("failed", {})
        raise


def should_collect_candidate(candidate):
    return candidate["has_federal_candidacy"] and (
        not candidate["recently_checked"] or bool(candidate.get("requested_fields"))
    )


def execute_source_collection(collector, *args) -> dict:
    try:
        return collector(*args)
    except Exception as error:
        failure = describe_error(error)
        emit_event("source_enrichment_failed", source=collector.__module__, **failure)
        return {"status": "failed", "failures": [failure]}
