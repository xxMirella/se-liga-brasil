"""Public voting projection: excerpts are not interpretations or verified impact."""

from urllib.parse import urlsplit

from service.analytical_datasets.contracts import VOTE_COLUMNS, validate_person_vote
from service.analytical_datasets.datasets import MAX_REPOSITORY_BYTES, publish_validated_dataset

PUBLIC_TIMELINE_SCHEMA = "person_voting_timeline.v1"
MATTER_INPUT_COLUMNS = {
    "matter_kind",
    "matter_number",
    "matter_year",
    "matter_name",
    "description",
    "description_origin",
    "official_url",
    "voting_subject",
    "round_number",
}
PUBLIC_TIMELINE_COLUMNS = {
    column: "VARCHAR"
    for column in (
        "person_id",
        "voting_id",
        "institution_code",
        "occurred_on",
        "date_precision",
        "vote_choice",
        "participation_status",
        "matter_kind",
        "matter_number",
        "matter_name",
        "matter_name_state",
        "matter_kind_state",
        "matter_number_state",
        "matter_year_state",
        "voting_subject",
        "voting_subject_state",
        "short_description",
        "description_kind",
        "description_state",
        "official_url",
        "official_url_state",
        "event_start_on",
        "event_end_on",
    )
} | {"matter_year": "INTEGER", "round_number": "INTEGER"}
MAX_DESCRIPTION_CHARACTERS = 280


def validate_nullable_text(value, field, max_characters=8000):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > max_characters:
        raise ValueError(f"Invalid nullable text: {field}")
    return value.strip()


def validate_official_url(value):
    value = validate_nullable_text(value, "official_url", 2048)
    if value is None:
        return None
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.fragment
        or not hostname.endswith((".leg.br", ".gov.br"))
    ):
        raise ValueError("Expected an official HTTPS legislative/government URL")
    return value


def project_description(description, origin):
    description = validate_nullable_text(description, "description")
    if origin not in {"official_text", "curated_summary", "unknown"}:
        raise ValueError("Unknown description origin")
    if description is None:
        if origin != "unknown":
            raise ValueError("Missing description must have unknown origin")
        return {
            "short_description": None,
            "description_kind": "unknown",
            "description_state": "missing",
        }
    if origin == "unknown":
        raise ValueError("Description needs official text or explicit curation")
    kind = origin
    if len(description) > MAX_DESCRIPTION_CHARACTERS:
        kind = "official_excerpt" if origin == "official_text" else "curated_excerpt"
    return {
        "short_description": description[:MAX_DESCRIPTION_CHARACTERS],
        "description_kind": kind,
        "description_state": "available",
    }


def project_public_voting_timeline(record, partition):
    if not isinstance(record, dict) or set(record) != VOTE_COLUMNS | MATTER_INPUT_COLUMNS:
        raise ValueError("Unexpected or missing voting timeline input fields")
    canonical_vote = validate_person_vote(
        {field: record[field] for field in VOTE_COLUMNS}, partition, allow_event_keys=True
    )
    result = {
        field: value
        for field, value in canonical_vote.items()
        if field not in {"evidence_sha256", "validation_status"}
    }
    for field in ("matter_kind", "matter_number", "matter_name", "voting_subject"):
        result[field] = validate_nullable_text(record[field], field)
        result[field + "_state"] = "available" if result[field] else "missing"
    year = record["matter_year"]
    if year is not None and (type(year) is not int or not 1800 <= year <= 2200):
        raise ValueError("Invalid matter year")
    result["matter_year"] = year
    result["matter_year_state"] = "available" if year else "missing"
    round_number = record["round_number"]
    if round_number is not None and (type(round_number) is not int or not 1 <= round_number <= 100):
        raise ValueError("Invalid voting round")
    result["round_number"] = round_number
    result.update(project_description(record["description"], record["description_origin"]))
    result["official_url"] = validate_official_url(record["official_url"])
    result["official_url_state"] = "available" if result["official_url"] else "missing"
    return result


def publish_person_voting_timeline(
    input_path,
    repository_path,
    partition,
    parser_version,
    *,
    max_repository_bytes=MAX_REPOSITORY_BYTES,
):
    return publish_validated_dataset(
        input_path,
        repository_path,
        partition,
        parser_version,
        max_repository_bytes=max_repository_bytes,
        schema_version=PUBLIC_TIMELINE_SCHEMA,
        validate_record=project_public_voting_timeline,
        column_types=PUBLIC_TIMELINE_COLUMNS,
    )
