"""Stage bounded normalized facts; ambiguous personal links stay out of ingestion."""

from uuid import uuid4

from service.ingestion.contracts import IngestionError, ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

PARSER_VERSION = "receita-cnpj-v1"


def stage_snapshot_facts(artifact, facts, configuration):
    if hash_file(artifact.path) != artifact.sha256:
        raise IngestionError("CNPJ_ARTIFACT_CHANGED")
    groups = {
        "companies": facts.companies,
        "establishments": facts.establishments,
        "partners": facts.relationships,
    }
    records = [
        fact
        for fact in groups[artifact.resource.kind]
        if fact["source_sha256"] == artifact.sha256
        and (artifact.resource.kind != "partners" or fact["identity_status"] == "reviewed")
    ]
    directory = configuration.storage_directory / "validated" / artifact.sha256 / uuid4().hex
    create_private_directory(directory)
    path, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    with path.open("x", encoding="utf-8") as output, rejected.open("x", encoding="utf-8"):
        path.chmod(0o600)
        rejected.chmod(0o600)
        for number, fact in enumerate(records, 1):
            data = {key: value for key, value in fact.items() if key != "candidate_person_ids"}
            data |= {
                "fact_kind": artifact.resource.kind,
                "snapshot_month": artifact.resource.dataset + "-01",
            }
            write_json_line(output, staged_business_record(artifact, data, number))
    return ValidatedArtifact(
        artifact,
        path,
        rejected,
        hash_file(path),
        hash_file(rejected),
        f"receita:{artifact.resource.dataset}:{artifact.resource.kind}:{hash_content(records)}",
        {"valid": len(records), "rejected": 0},
        PARSER_VERSION,
    )


def staged_business_record(artifact, data, row_number):
    key = data.get("observation_key") or data.get("cnpj") or data["company_base"]
    # Entity versions belong to a snapshot; personal links include reviewed evidence.
    external_key = artifact.resource.dataset + ":" + key
    if data["fact_kind"] == "partners":
        external_key += ":" + hash_content(
            [data["person_id"], data["identity_evidence"], data["reviewed_by"], data["reviewed_at"]]
        )
    return {
        "kind": artifact.resource.kind,
        "externalKey": external_key,
        "normalizedData": data,
        "contentSha256": hash_content(data),
        "sourceGeneratedAt": artifact.fetched_at,
        "entryName": artifact.path.name,
        "rowNumber": row_number,
    }
