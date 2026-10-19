"""Enrich requested people from immutable local evidence, without remote calls."""

from dataclasses import asdict
from pathlib import Path

from crawlers.alesp.configuration import ALESP_PARSER_VERSION
from crawlers.alesp.institutional_records import institutional_profiles
from crawlers.alesp.local_records import authored_propositions
from service.ingestion.contracts import (
    DownloadedArtifact,
    IngestionError,
    Resource,
    ValidatedArtifact,
)
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
    for source in resolution_sources(resolutions):
        if hash_file(Path(source["path"])) != source["sha256"]:
            raise IngestionError("ALESP_LOCAL_EVIDENCE_CHECKSUM_MISMATCH")
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


def collect_alesp_local_enrichment(repository, storage_directory, person_ids=None, fields=None):
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
    return result | {"status": "completed", "remote_requests": 0}
