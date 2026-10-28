"""Delegate durable gaps once per source, with leases, cache and retry cooldowns."""

from datetime import date
from uuid import uuid4

from crawlers.alerj.pipeline import collect_alerj_enrichment
from crawlers.alesp.enrichment import collect_alesp_enrichment
from crawlers.tse.enrichment import collect_requested_tse_data
from crawlers.tse_filiation.enrichment import collect_tse_filiation
from database.completeness import fetch_completeness_rows
from database.data_gaps import (
    block_data_gaps,
    claim_data_gaps,
    defer_unmatched_institutional_people,
    postpone_source,
    release_data_gaps,
    route_data_gaps,
)
from database.enrichment import fetch_enrichment_candidates
from database.operations import refresh_person_profiles
from service.completeness.assessment import assess_completeness
from service.enrichment.pipeline import execute_source_collection, run_camara_collection
from service.maintenance.data_gap_cleanup import purge_processed_gaps
from service.orchestration.career_collection import dispatch_career_resources
from storage.files import save_json


def group_source_requests(tasks) -> dict:
    requests = {}
    for task in tasks:
        source = requests.setdefault(task["assigned_source"], {})
        source.setdefault(task["person_id"], set()).add(task["field_name"])
    return requests


def ordered_source_candidates(candidates, people):
    indexed = {row["person_id"]: row for row in candidates}
    return [indexed[person_id] for person_id in people if person_id in indexed]


def collect_requested_source(connection, storage, source, people, rows, candidates):
    candidates = ordered_source_candidates(candidates, people)
    if source == "tse":
        from crawlers.tse.requested_data import load_requested_election_scope

        targets = [
            {
                "person_id": row["person_id"],
                "election_year": row["election_year"],
                "fields": sorted(people[row["person_id"]]),
            }
            for row in load_requested_election_scope(connection, list(people))
            if row["election_year"]
        ]
        return execute_source_collection(collect_requested_tse_data, connection, storage, targets)
    if source == "alesp":
        fields = set().union(*people.values())
        return execute_source_collection(collect_alesp_enrichment, connection, list(people), fields)
    if source == "camara":
        return execute_source_collection(
            run_camara_collection,
            connection,
            storage,
            [
                row | {"requested_fields": sorted(people[row["person_id"]])}
                for row in candidates
                if row["person_id"] in people
            ],
        )
    if source == "alerj":
        return execute_source_collection(
            collect_alerj_enrichment,
            connection,
            storage,
            [row for row in candidates if row["person_id"] in people],
            set().union(*people.values()),
        )
    if source == "senado":
        from crawlers.senado.pipeline import collect_senado_enrichment

        return execute_source_collection(
            collect_senado_enrichment,
            connection,
            storage,
            [
                row | {"requested_fields": sorted(people[row["person_id"]])}
                for row in candidates
                if row["person_id"] in people
            ],
            set().union(*people.values()),
        )
    if source == "tse_filiation":
        return execute_source_collection(collect_tse_filiation, connection, storage, people)
    return {"status": "blocked", "failures": [{"code": "SOURCE_COLLECTOR_NOT_AVAILABLE"}]}


def apply_source_cooldown(connection, source, result) -> None:
    failures = result.get("failures", [])
    if not failures or result.get("status") == "blocked":
        return
    retry_after = max((row.get("retry_after_seconds", 0) for row in failures), default=0)
    delay = max(3600, retry_after)
    postpone_source(
        connection,
        source,
        delay,
        failures[0].get("code", "SOURCE_COLLECTION_FAILED"),
        failures[0].get("status"),
    )


def release_deferred_people(connection, results) -> None:
    for source, result in results.items():
        if result.get("failures"):
            continue
        people = result.get("deferred_person_ids", [])
        if people:
            connection.execute(
                """
                UPDATE se_liga_brasil.person_data_gap SET next_attempt_at=now()
                WHERE assigned_source=%s AND status='queued' AND person_id=ANY(%s::uuid[])
                """,
                (source, people),
            )


def block_unavailable_fields(connection, worker_id, source, people, result):
    fields = result.get("unsupported_fields", [])
    error = "SOURCE_FIELD_NOT_SUPPORTED"
    if result.get("status") == "blocked":
        fields = set().union(*people.values())
        failures = result.get("failures", [])
        error = failures[0]["code"] if failures else "SOURCE_COLLECTOR_NOT_AVAILABLE"
    if fields:
        block_data_gaps(connection, worker_id, source, fields, error)


def orchestrate_collection(
    connection,
    storage,
    person_id=None,
    task_limit=1000,
    *,
    refresh_assessment=True,
    field_names=None,
    source_codes=None,
    career_collectors=None,
) -> dict:
    before = initial_assessment(connection, storage, person_id, refresh_assessment)
    purge_processed_gaps(connection)
    route_data_gaps(connection)
    worker_id = str(uuid4())
    tasks = claim_data_gaps(connection, worker_id, person_id, task_limit, field_names, source_codes)
    requests = group_source_requests(tasks)
    if not tasks:
        result = {
            "before": before,
            "claimed_tasks": 0,
            "collection": {},
            "status": "completed",
            "coverage_message": "No due tasks; unresolved gaps may have cooldowns.",
        }
        save_json(storage / "enrichment-result.json", result)
        return result
    results = {}
    try:
        rows = fetch_completeness_rows(connection, person_id)
        candidates = fetch_enrichment_candidates(connection, person_id)
        for source, people in requests.items():
            results[source] = collect_requested_source(
                connection, storage, source, people, rows, candidates
            )
            apply_source_cooldown(connection, source, results[source])
            block_unavailable_fields(connection, worker_id, source, people, results[source])
            defer_unmatched_institutional_people(
                connection, worker_id, source, results[source].get("unmatched_person_ids", [])
            )
        collect_career_resources(connection, tasks, results, career_collectors)
        refresh_person_profiles(connection)
        after = assess_completeness(connection, storage, person_id)
    finally:
        release_data_gaps(connection, worker_id)
        release_deferred_people(connection, results)
    result = {
        "before": before,
        "after": after,
        "claimed_tasks": len(tasks),
        "source_requests": {source: len(people) for source, people in requests.items()},
        "collection": results,
        "status": collection_status(after, results),
    }
    save_json(storage / "enrichment-result.json", result)
    return result


def collection_status(assessment, results):
    incomplete = any(
        row.get("failures")
        or row.get("status") in {"partial", "failed", "blocked"}
        or row.get("deferred")
        or row.get("unsupported")
        for row in results.values()
    )
    all_people_complete = assessment["complete_people"] == assessment["total_people"]
    missing_fields = any(assessment.get("missing_by_field", {}).values())
    return (
        "completed" if all_people_complete and not incomplete and not missing_fields else "partial"
    )


def initial_assessment(connection, storage, person_id, refresh):
    if refresh:
        return assess_completeness(connection, storage, person_id)
    return {"assessment": "existing_persistent_queue"}


def collect_career_resources(connection, tasks, results, collectors):
    if collectors is not None:
        results["career"] = execute_source_collection(
            dispatch_career_resources, connection, tasks, date.today(), collectors
        )
