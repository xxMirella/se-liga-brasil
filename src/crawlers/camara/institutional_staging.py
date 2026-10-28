"""Stage independent official identities through the shared canonical resolver."""

from service.identity_resolution.evidence import IdentityEvidenceBuilder, load_identity_key
from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

PARSER_VERSION = "camara-institutional-python-v1"


def stage_institutional_profile(artifact, configuration, data, document):
    return stage_institutional_profiles(artifact, configuration, [(data, document)])


def stage_institutional_profiles(artifact, configuration, rows):
    directory = (
        configuration.storage_directory / "validated" / (artifact.sha256 + "-" + PARSER_VERSION)
    )
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    builder = IdentityEvidenceBuilder(load_identity_key())
    with records.open("w", encoding="utf-8") as output:
        records.chmod(0o600)
        for number, (data, document) in enumerate(rows, 1):
            evidence = builder.build_evidence(data["civilName"], cpf=document["dados"].get("cpf"))
            write_json_line(
                output,
                {
                    "kind": "camara_institutional_profile",
                    "externalKey": data["officialDeputyCode"],
                    "normalizedData": data,
                    "contentSha256": hash_content(data),
                    "sourceGeneratedAt": artifact.fetched_at,
                    "entryName": artifact.path.name,
                    "rowNumber": number,
                    "identityEvidence": evidence,
                },
            )
    rejected.write_text("")
    rejected.chmod(0o600)
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        "camara:national-institutional-roster",
        {"valid": len(rows), "rejected": 0},
        PARSER_VERSION,
    )
