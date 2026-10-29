"""Read/write of the normalized per-year files (JSON lines and gzip CSV), streaming."""

import csv
import gzip
import json
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path

from service.party_vote_analysis.choices import Choice
from service.party_vote_analysis.contracts import OrientationRecord, VoteRecord

VOTE_COLUMNS = ["voting_id", "voted_on", "member_id", "party_at_vote", "state", "choice"]


def votes_path(directory: Path, chamber: str, year: int) -> Path:
    return directory / chamber / f"votes-{year}.csv.gz"


def votings_path(directory: Path, chamber: str, year: int) -> Path:
    return directory / chamber / f"votings-{year}.jsonl"


def orientations_path(directory: Path, year: int) -> Path:
    return directory / "camara" / f"orientations-{year}.jsonl"


def write_votes(path: Path, votes: Iterable[VoteRecord]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(path, "wt", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(VOTE_COLUMNS)
        for vote in votes:
            writer.writerow(
                [
                    vote.voting_id,
                    vote.voted_on.isoformat(),
                    vote.member_id,
                    vote.party_at_vote,
                    vote.state,
                    vote.choice.value,
                ]
            )
            count += 1
    return count


def read_votes(path: Path, chamber: str) -> Iterator[VoteRecord]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            yield VoteRecord(
                chamber,
                row["voting_id"],
                date.fromisoformat(row["voted_on"]),
                row["member_id"],
                row["party_at_vote"],
                row["state"],
                Choice(row["choice"]),
            )


def write_json_lines(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def read_json_lines(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as source:
        for line in source:
            yield json.loads(line)


def orientation_row(record: OrientationRecord) -> dict:
    return {"voting_id": record.voting_id, "bloc": record.bloc, "orientation": record.orientation}
