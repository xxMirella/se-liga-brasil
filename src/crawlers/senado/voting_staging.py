"""Stage sanitized voting facts with internal personal identity and parser scope."""

from uuid import uuid4

from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

PARSER_VERSION = "senado-voting-v1"


def stage_voting_records(artifact, configuration, votings, individual_votes):
    directory = configuration.storage_directory / "validated" / artifact.sha256 / uuid4().hex
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    facts = [("senado_voting", item) for item in votings]
    facts.extend(("senado_person_vote", item) for item in individual_votes)
    with records.open("x", encoding="utf-8") as output:
        records.chmod(0o600)
        for number, (kind, data) in enumerate(facts, 1):
            key = (
                data["source_key"]
                if kind == "senado_voting"
                else hash_content(
                    [
                        data["voting_key"],
                        data["person_id"],
                        data["identity_profile_sha256"],
                    ]
                )
            )
            write_json_line(
                output,
                {
                    "kind": kind,
                    "externalKey": key,
                    "normalizedData": data,
                    "contentSha256": hash_content(data),
                    "sourceGeneratedAt": artifact.fetched_at,
                    "entryName": artifact.path.name,
                    "rowNumber": number,
                },
            )
    rejected.write_text("", encoding="utf-8")
    rejected.chmod(0o600)
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        "senado:voting:"
        + hash_content(
            sorted((x["person_id"], x["identity_profile_sha256"]) for x in individual_votes)
        ),
        {"valid": len(facts), "rejected": 0},
        PARSER_VERSION,
    )


class SenateVotingProjection:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("senado_legislative_voting", parameters)
