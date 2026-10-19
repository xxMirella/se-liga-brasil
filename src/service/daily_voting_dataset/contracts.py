"""Daily append/retification contracts; original artifact observation orders revisions."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from service.analytical_datasets import DatasetPartition
from service.analytical_datasets.public_voting_timeline import project_public_voting_timeline
from service.analytical_datasets.storage import DatasetManifest


@dataclass(frozen=True)
class DailyVotingPartition:
    institution_code: str
    occurred_on: date

    def __post_init__(self):
        if type(self.occurred_on) is not date:
            raise ValueError("A precise voting day is required")
        DatasetPartition(self.institution_code, self.occurred_on.year)

    @property
    def relative_path(self):
        return (
            f"legislative/{self.institution_code}/person_voting_timeline/"
            f"year={self.occurred_on.year}/month={self.occurred_on.month:02}/"
            f"day={self.occurred_on.day:02}"
        )


@dataclass(frozen=True)
class DailyDatasetManifest(DatasetManifest):
    private_state_sha256: str
    private_state_file: str
    occurred_on: str


def project_daily_vote(record, partition):
    import hashlib
    import json

    if not isinstance(record, dict) or "source_observed_at" not in record:
        raise ValueError("Original artifact observation timestamp is required")
    incoming = dict(record)
    observed_at = incoming.pop("source_observed_at")
    if not isinstance(observed_at, str):
        raise ValueError("Observation timestamp must be an ISO timestamp")
    observation = datetime.fromisoformat(observed_at)
    if observation.tzinfo is None:
        raise ValueError("Observation timestamp must include timezone")
    year_partition = DatasetPartition(partition.institution_code, partition.occurred_on.year)
    projected = project_public_voting_timeline(incoming, year_partition)
    if projected["date_precision"] != "day" or projected["occurred_on"] != str(
        partition.occurred_on
    ):
        raise ValueError("Daily partition accepts only its exact, verified voting day")
    encoded = json.dumps(projected, sort_keys=True, separators=(",", ":")).encode()
    return projected | {
        "source_observed_at": observation.astimezone(UTC).isoformat(timespec="microseconds"),
        "record_sha256": hashlib.sha256(encoded).hexdigest(),
        "evidence_sha256": incoming["evidence_sha256"],
    }
