"""Reconcile cached and newly acquired historical participation proofs."""

from collections import Counter
from pathlib import Path

from crawlers.alesp.participation_records import (
    document_participation_rows,
    participation_identity_indexes,
    structured_participation_rows,
)
from crawlers.alesp.participation_sources import cached_participation_sources
from service.observability.reporting import describe_error


def collect_participation_evidence(
    repository, storage_directory, resolutions, person_ids, stage_records, acquire=None
):
    registrations, names = participation_identity_indexes(resolutions, person_ids)
    acquisition = acquire(registrations) if acquire and registrations else {}
    references = list(cached_participation_sources(storage_directory))
    rows, failures = {}, list(acquisition.get("failures", []))
    channels = Counter()
    for reference in references:
        try:
            parsed = parse_participation_reference(reference, registrations, names)
            for row in parsed:
                rows[row["officialKey"]] = row
        except Exception as error:
            failures.append({"url": reference["url"], "error": describe_error(error)})
    for row in rows.values():
        channels[row["channel"]] += 1
    if rows:
        artifact = stage_records(
            storage_directory, "alesp_participation", rows.values(), references, person_ids
        )
        repository.ingest_validated_artifact(artifact, 500)
    return acquisition | {
        "people_with_evidence": len({row["personId"] for row in rows.values()}),
        "evidence_records": len(rows),
        "channels": dict(channels),
        "failures": failures,
        "coverage": "positive_evidence_only",
    }


def parse_participation_reference(reference, registrations, names):
    reference = reference | {"path": Path(reference["path"])}
    if reference["kind"] in {"commission_export", "plenary_register", "meeting_participants"}:
        return structured_participation_rows(reference, registrations, names)
    if reference["kind"] in {"minutes", "transcript", "event_participants"}:
        return document_participation_rows(reference, names)
    return []
