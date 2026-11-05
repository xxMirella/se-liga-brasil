"""Enrich requested people from immutable local evidence before any attendance download."""

from dataclasses import asdict
from pathlib import Path

from crawlers.alesp.attendance import (
    archived_attendance_exports,
    attendance_identity_index,
    committee_attendance_rows,
)
from crawlers.alesp.configuration import ALESP_PARSER_VERSION
from crawlers.alesp.institutional_records import institutional_profiles
from crawlers.alesp.local_records import authored_propositions
from crawlers.alesp.photos import cached_photo_records
from service.ingestion.contracts import (
    DownloadedArtifact,
    IngestionError,
    Resource,
    ValidatedArtifact,
)
from service.observability.reporting import describe_error
from storage.files import (
    create_private_directory,
    hash_content,
    hash_file,
    load_json,
    save_json,
    write_json_line,
)


def verified_evidence_references(resolutions):
    references = {}
    checked = set()
    for source in resolution_sources(resolutions):
        key = (source["path"], source["sha256"])
        if key not in checked:
            if hash_file(Path(source["path"])) != source["sha256"]:
                raise IngestionError("ALESP_LOCAL_EVIDENCE_CHECKSUM_MISMATCH")
            checked.add(key)
        references[source["sha256"]] = source
    return list(references.values())


def resolution_sources(resolutions):
    for resolution in resolutions:
        for subject in resolution.get("official_subjects", []):
            yield from subject.get("sources", [])


def dataset_references(storage_directory):
    research = storage_directory / "research"
    manifest = load_json(research / "catalog-download-manifest.json", [])
    names = {"61_deputados.xml", "56_proposituras.zip", "81_documento_autor.zip"}
    references = []
    for entry in manifest:
        if Path(entry["file"]).name not in names:
            continue
        path = research / entry["file"]
        if hash_file(path) != entry["sha256"]:
            raise IngestionError("ALESP_LOCAL_EVIDENCE_CHECKSUM_MISMATCH")
        references.append(
            {
                "url": entry["url"],
                "path": str(path),
                "sha256": entry["sha256"],
                "fetched_at": entry["collected_at"],
            }
        )
    if len(references) != len(names):
        raise IngestionError("ALESP_LOCAL_DATASET_MANIFEST_MISSING")
    return references


def stage_local_records(storage_directory, kind, rows, references, person_ids):
    scope = hash_content(sorted(person_ids) if person_ids is not None else "verified_people")
    bundle = storage_directory / "bundles" / (hash_content([kind, references, scope]) + ".json")
    if not bundle.exists():
        save_json(bundle, references)
    directory = storage_directory / "validated" / (bundle.stem + "-local-v1")
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    observed_at = min(reference["fetched_at"] for reference in references)
    count = 0
    with records.open("w", encoding="utf-8") as output:
        records.chmod(0o600)
        for count, data in enumerate(rows, start=1):
            write_json_line(
                output,
                {
                    "kind": kind,
                    "externalKey": hash_content(
                        [data["personId"], data.get("officialKey", "profile")]
                    ),
                    "normalizedData": data,
                    "contentSha256": hash_content(data),
                    "sourceGeneratedAt": data.get("observedAt", observed_at),
                    "entryName": bundle.name,
                    "rowNumber": count,
                },
            )
    rejected.write_text("")
    rejected.chmod(0o600)
    resource = Resource(
        "alesp-local-" + kind,
        "ALESP local enrichment",
        references[0]["url"],
        kind,
        2026,
        "alesp-local-enrichment",
        "SP",
        ".json",
    )
    artifact = DownloadedArtifact(
        resource, bundle, hash_file(bundle), observed_at, bundle.stat().st_size, "cached"
    )
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        scope,
        {"valid": count, "rejected": 0},
        ALESP_PARSER_VERSION,
    )


def collect_alesp_local_enrichment(
    repository, storage_directory, person_ids=None, fields=None, *, fetch_attendance=None,
):
    person_ids = {str(value) for value in person_ids} if person_ids is not None else None
    fields = set(
        fields or {"current_political_party", "current_public_office", "political_activity"}
    )
    resolutions = load_json(storage_directory / "identity-resolution.json", {}).get(
        "resolutions", []
    )
    evidence = verified_evidence_references(resolutions)
    if not evidence:
        return {"status": "unavailable", "reason": "no_verified_local_identity_evidence"}
    result = {}
    if "photo_url" in fields:
        rows = cached_photo_records(resolutions, person_ids)
        staged = stage_local_records(storage_directory, "alesp_photos", rows, evidence, person_ids)
        result["photos"] = asdict(repository.ingest_validated_artifact(staged, 500))
    if fields & {"current_political_party", "current_public_office"}:
        rows = institutional_profiles(resolutions, person_ids)
        staged = stage_local_records(storage_directory, "alesp_profile", rows, evidence, person_ids)
        result["profiles"] = asdict(repository.ingest_validated_artifact(staged, 500))
    if "political_activity" in fields:
        references = dataset_references(storage_directory) + evidence
        rows = authored_propositions(
            storage_directory / "research/datasets", resolutions, person_ids
        )
        staged = stage_local_records(
            storage_directory, "alesp_propositions", rows, references, person_ids
        )
        result["authorships"] = asdict(repository.ingest_validated_artifact(staged, 500))
        result["staged_authorships"] = staged.summary["valid"]
    if "attendance" in fields:
        result["attendance"] = collect_committee_attendance(
            repository, storage_directory, resolutions, evidence, person_ids, fetch_attendance
        )
    attendance = result.get("attendance", {})
    return result | {
        "status": "partial" if attendance.get("failures") else "completed",
        "remote_requests": attendance.get("remote_requests", 0),
    }


def collect_committee_attendance(
    repository, storage_directory, resolutions, evidence, person_ids, fetch_attendance,
):
    identities = attendance_identity_index(resolutions, person_ids)
    exports = list(archived_attendance_exports(storage_directory)) if identities else []
    rows = committee_attendance_rows([Path(item["path"]) for item in exports], identities)
    missing = set(identities.values()) - {row["personId"] for row in rows}
    failures = []
    remote_requests = int(bool(missing and fetch_attendance))
    if remote_requests:
        try:
            downloaded = fetch_attendance()
            remaining = {key: person for key, person in identities.items() if person in missing}
            rows.extend(committee_attendance_rows([Path(downloaded["path"])], remaining))
            exports.append(downloaded)
        except Exception as error:
            failures.append(describe_error(error))
    if rows:
        observed_at = max(item["fetched_at"] for item in exports)
        for row in rows:
            row["observedAt"] = observed_at
        artifact = stage_local_records(
            storage_directory, "alesp_attendance", rows, exports + evidence, person_ids
        )
        repository.ingest_validated_artifact(artifact, 500)
    return {
        "people_with_evidence": len({row["personId"] for row in rows}),
        "person_months": len(rows),
        "remote_requests": remote_requests,
        "failures": failures,
    }
