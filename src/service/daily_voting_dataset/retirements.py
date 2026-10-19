"""Explicit source-backed event retirements; never inferred from an absent row."""

import hashlib
import json
from datetime import UTC, datetime

from service.analytical_datasets.contracts import validate_voting_key
from service.daily_voting_dataset.merge import STATE_COLUMNS

RETIREMENT_PERSON_KEY = "__retired_voting__"
MAX_RETIRED_VOTINGS = 1000


def normalize_retirements(voting_ids, observed_at):
    identifiers = set()
    for position, voting_id in enumerate(voting_ids):
        if position >= MAX_RETIRED_VOTINGS:
            raise ValueError("Retirement batch exceeds 1000 voting events")
        identifiers.add(validate_voting_key(voting_id, allow_event_keys=True))
    if not identifiers:
        if observed_at is not None:
            raise ValueError("Retirement timestamp supplied without retired events")
        return (), None
    if not isinstance(observed_at, str):
        raise ValueError("Explicit retirement source observation timestamp is required")
    observation = datetime.fromisoformat(observed_at)
    if observation.tzinfo is None:
        raise ValueError("Retirement observation must include timezone")
    return tuple(sorted(identifiers)), observation.astimezone(UTC).isoformat(
        timespec="microseconds"
    )


def append_retirement_checkpoints(path, voting_ids, observed_at):
    with path.open("a") as target:
        for voting_id in voting_ids:
            record = dict.fromkeys(STATE_COLUMNS)
            record.update(
                person_id=RETIREMENT_PERSON_KEY,
                voting_id=voting_id,
                source_observed_at=observed_at,
                record_sha256=hashlib.sha256(b"explicit_voting_retirement").hexdigest(),
            )
            target.write(json.dumps(record, sort_keys=True) + "\n")
