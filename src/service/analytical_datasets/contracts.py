"""Strict public analytical contracts; no provider personal identifiers."""

import calendar
import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID

SCHEMA_VERSION = "person_votes.v1"
VOTE_COLUMNS = {
    "person_id",
    "voting_id",
    "institution_code",
    "occurred_on",
    "date_precision",
    "vote_choice",
    "participation_status",
    "evidence_sha256",
    "validation_status",
}
VOTE_CHOICES = {None, "yes", "no", "abstention", "obstruction"}
PARTICIPATION_STATES = {
    "voted",
    "presiding",
    "absent",
    "not_recorded",
    "parliamentary_activity",
    "excused",
    "unknown",
}


@dataclass(frozen=True)
class DatasetPartition:
    institution_code: str
    year: int
    collection_complete: bool = False

    def __post_init__(self):
        if not isinstance(self.institution_code, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]{1,39}", self.institution_code
        ):
            raise ValueError("Invalid institution_code")
        if type(self.year) is not int or not 1900 <= self.year <= 2200:
            raise ValueError("Invalid partition year")
        if type(self.collection_complete) is not bool:
            raise ValueError("Collection completeness must be an explicit boolean")

    @property
    def relative_path(self):
        return f"legislative/{self.institution_code}/person_votes/year={self.year}"


def event_bounds(value: str, precision: str) -> tuple[str, str]:
    patterns = {"day": r"\d{4}-\d{2}-\d{2}", "month": r"\d{4}-\d{2}", "year": r"\d{4}"}
    if not isinstance(precision, str) or precision not in patterns or not isinstance(value, str):
        raise ValueError("Unsupported date precision")
    if not re.fullmatch(patterns[precision], value):
        raise ValueError("Date does not match precision")
    if precision == "day":
        start = end = date.fromisoformat(value)
    elif precision == "month":
        start = date.fromisoformat(value + "-01")
        end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    else:
        start, end = date(int(value), 1, 1), date(int(value), 12, 31)
    return start.isoformat(), end.isoformat()


def validate_vote_fields(record: dict):
    if not isinstance(record, dict) or set(record) != VOTE_COLUMNS:
        raise ValueError("Unexpected or missing person_vote fields")
    if record["validation_status"] != "verified":
        raise ValueError("Only verified facts can enter analytical datasets")
    text_fields = VOTE_COLUMNS - {"vote_choice", "voting_id"}
    if any(not isinstance(record[field], str) for field in text_fields):
        raise ValueError("Expected scalar text fields")
    if record["vote_choice"] is not None and not isinstance(record["vote_choice"], str):
        raise ValueError("Expected a scalar vote choice")


def validate_voting_key(value, *, allow_event_keys=False):
    voting_id = str(value)
    if re.fullmatch(r"[1-9][0-9]{0,18}", voting_id) and int(voting_id) <= 2**63 - 1:
        return voting_id
    if allow_event_keys and re.fullmatch(
        r"(?:senado:(?:plenary|committee)|camara:voting):[A-Za-z0-9_.:-]{1,100}", voting_id
    ):
        return voting_id
    raise ValueError("Expected canonical voting_id or an allowed technical voting event key")


def validate_person_vote(
    record: dict, partition: DatasetPartition, *, allow_event_keys=False
) -> dict:
    validate_vote_fields(record)
    result = dict(record)
    result["person_id"] = str(UUID(record["person_id"]))
    result["voting_id"] = validate_voting_key(
        record["voting_id"], allow_event_keys=allow_event_keys
    )
    if record["institution_code"] != partition.institution_code:
        raise ValueError("Institution differs from partition")
    start, end = event_bounds(record["occurred_on"], record["date_precision"])
    if int(start[:4]) != partition.year:
        raise ValueError("Event differs from partition year")
    if record["vote_choice"] not in VOTE_CHOICES:
        raise ValueError("Invalid vote choice")
    if record["participation_status"] not in PARTICIPATION_STATES:
        raise ValueError("Invalid participation status")
    if (record["vote_choice"] is not None) != (record["participation_status"] == "voted"):
        raise ValueError("Vote choice and participation contradict each other")
    if not re.fullmatch(r"[a-f0-9]{64}", record["evidence_sha256"]):
        raise ValueError("Invalid evidence hash")
    result.update(event_start_on=start, event_end_on=end)
    return result
