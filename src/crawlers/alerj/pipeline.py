"""Batch ALERJ collection: one roster and payroll for personally verified targets."""

from dataclasses import asdict
from datetime import datetime
from uuid import uuid4

import httpx

from crawlers.alerj.acquisition import AlerjAcquisition
from crawlers.alerj.configuration import (
    OFFICIAL_HOSTS,
    PARSER_VERSION,
    PAYROLL_INDEX_URL,
    ROSTER_URL,
    SOURCE,
    CrawlerConfiguration,
)
from crawlers.alerj.parsing import latest_payroll_document, parse_profile, parse_roster
from crawlers.alerj.payroll import extract_pdf_text, parse_deputy_payroll
from crawlers.alerj.projection import AlerjProjectionWriter
from crawlers.alerj.staging import stage_records
from database.enrichment import match_official_person
from normalization.identity import normalize_person_name
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadedArtifact, IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_content, hash_file, save_json

SUPPORTED_FIELDS = frozenset({"current_salary", "current_political_party"})


def index_candidate_names(people):
    index = {}
    for person in people:
        names = [person.get("civil_name"), person.get("display_name")]
        names.extend(person.get("civil_names") or [])
        names.extend(person.get("public_names") or [])
        for name in names:
            if name:
                index.setdefault(normalize_person_name(name), {})[person["person_id"]] = person
    return index


def match_roster_targets(members, people):
    names = index_candidate_names(people)
    targets = []
    for member in members:
        matches = names.get(normalize_person_name(member["display_name"]), {})
        if len(matches) == 1:
            targets.append((next(iter(matches.values())), member))
    return targets


def select_person_payroll(person, payroll):
    names = [person.get("civil_name"), *(person.get("civil_names") or [])]
    keys = {normalize_person_name(name) for name in names if name}
    matches = [payroll[key] for key in keys if key in payroll]
    if len(matches) != 1:
        raise IngestionError("ALERJ_PAYROLL_IDENTITY_REVIEW_REQUIRED")
    return matches[0]


def collect_shared_evidence(acquisition, people):
    roster = acquisition.acquire(ROSTER_URL, "alerj_roster")
    roster_bytes = roster.path.read_bytes()
    members = parse_roster(roster_bytes)
    targets = match_roster_targets(members, people)
    if not targets:
        return members, targets, {}, None, roster
    index = acquisition.acquire(PAYROLL_INDEX_URL, "alerj_payroll_index")
    competence, url = latest_payroll_document(index.path.read_bytes())
    document = acquisition.acquire(url, "alerj_payroll", ".pdf")
    payroll = parse_deputy_payroll(extract_pdf_text(document.path))
    if any(row["competence"] != competence for row in payroll.values()):
        raise IngestionError("ALERJ_PAYROLL_COMPETENCE_MISMATCH")
    return members, targets, payroll, document, roster


def collect_verified_person(acquisition, repository, person, member, payroll, document, roster):
    salary = select_person_payroll(person, payroll).copy()
    artifact = acquisition.acquire(member["url"], "alerj_profile")
    profile = parse_profile(artifact.path.read_bytes(), member["display_name"])
    method = match_official_person(
        repository.connection,
        {"nomeCivil": salary["recipientName"], "dataNascimento": profile["birthDate"]},
        person["person_id"],
    )
    profile.update(
        {
            "personId": person["person_id"],
            "civilName": salary["recipientName"],
            "identityMethod": method,
            "representedUf": "RJ",
            "institutionCode": "alerj",
            "observedOn": datetime.fromisoformat(roster.fetched_at).date().isoformat(),
            "inExercise": None,
            "officeKind": "state_deputy",
            "evidence": [
                {"url": item.resource.url, "sha256": item.sha256}
                for item in (artifact, document, roster)
            ],
        }
    )
    salary.update(
        {
            "personId": person["person_id"],
            "recipientKey": person["person_id"],
            "representedUf": "RJ",
            "identityMethod": method,
        }
    )
    return {
        "person_id": person["person_id"],
        "profile": ingest_records(
            repository,
            acquisition,
            bundle_profile_evidence(acquisition, [artifact, document, roster]),
            [profile],
        ),
        "salary": ingest_records(repository, acquisition, document, [salary]),
    }


def ingest_records(repository, acquisition, artifact, rows):
    validated = stage_records(artifact, acquisition.configuration, rows)
    return asdict(
        repository.ingest_validated_artifact(validated, acquisition.configuration.batch_size)
    )


def collect_targets(acquisition, repository, people):
    members, targets, payroll, document, roster = collect_shared_evidence(acquisition, people)
    target_ids = {person["person_id"] for person, _ in targets}
    results, unresolved = [], []
    for person, member in targets[: acquisition.configuration.max_people]:
        try:
            results.append(
                collect_verified_person(
                    acquisition, repository, person, member, payroll, document, roster
                )
            )
        except IngestionError as error:
            if error.code in {"HTTP_ERROR", "SOURCE_COOLDOWN_ACTIVE"}:
                raise
            unresolved.append({"person_id": person["person_id"], "reason": error.code})
    return {
        "people": results,
        "identity_unresolved": unresolved,
        "roster_count": len(members),
        "payroll_count": len(payroll),
        "deferred": max(0, len(targets) - acquisition.configuration.max_people),
        "deferred_person_ids": [
            person["person_id"] for person, _ in targets[acquisition.configuration.max_people :]
        ],
        "unmatched_people": len(people) - len(targets),
        "unmatched_person_ids": [
            person["person_id"] for person in people if person["person_id"] not in target_ids
        ],
        "unsupported_fields": ["political_activity", "current_public_office"],
        "status": "partial" if unresolved or len(results) != len(people) else "completed",
    }


def collect_alerj_enrichment(connection, storage, people, fields=None):
    if fields is not None and not SUPPORTED_FIELDS.intersection(fields):
        return {
            "status": "blocked",
            "unsupported_fields": sorted(fields),
            "people": [],
            "deferred_person_ids": [],
        }
    if not people:
        return {"status": "completed", "people": [], "deferred_person_ids": []}
    configuration = CrawlerConfiguration(storage / "alerj")
    repository = IngestionRepository(
        connection,
        SOURCE,
        AlerjProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "requested_state_institutional_data"})
    try:
        with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
            acquisition = AlerjAcquisition(
                configuration, OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
            )
            result = collect_targets(acquisition, repository, people)
        repository.finish_run(result["status"], result)
        return result
    except BaseException:
        repository.finish_run("failed", {})
        raise


def bundle_profile_evidence(acquisition, artifacts):
    references = [
        {"url": item.resource.url, "sha256": item.sha256, "path": str(item.path)}
        for item in artifacts
    ]
    path = (
        acquisition.configuration.storage_directory
        / "bundles"
        / (hash_content(references) + ".json")
    )
    if not path.exists():
        save_json(path, references)
    return DownloadedArtifact(
        artifacts[0].resource,
        path,
        hash_file(path),
        max(item.fetched_at for item in artifacts),
        path.stat().st_size,
    )
