"""Dispatch only new or changed facts to exact day partitions."""

import json
from contextlib import ExitStack
from datetime import date
from pathlib import Path

from service.daily_voting_dataset import DailyVotingPartition, consolidate_daily_votes
from service.voting_pipeline.change_index import VotingChangeIndex
from storage.files import write_json_line

MAX_ROWS = 100000
MAX_LINE_BYTES = 16384


def prepare_daily_changes(input_path, source, start, end, temporary, index):
    handles, files, facts, retirements = {}, {}, {}, {}
    with ExitStack() as stack, Path(input_path).open("r", encoding="utf-8") as incoming:
        for count, line in enumerate(incoming, 1):
            if count > MAX_ROWS or len(line.encode()) > MAX_LINE_BYTES:
                raise ValueError("Voting input exceeds its record budget")
            record = json.loads(line)
            day = validate_record_scope(record, source, start, end)
            change = index.inspect_record(record)
            if change is None:
                continue
            fact, previous_day = change
            key = fact[:3]
            if key in facts and facts[key] != fact:
                raise ValueError("Conflicting duplicate voting facts in acquisition")
            facts[key] = fact
            if previous_day:
                retirements[(previous_day, record["voting_id"])] = fact[4]
            if day not in handles:
                path = temporary / (day + ".ndjson")
                handles[day] = stack.enter_context(path.open("x", encoding="utf-8"))
                path.chmod(0o600)
                files[day] = path
            write_json_line(handles[day], record)
    return files, list(facts.values()), retirements


def validate_record_scope(record, source, start, end):
    if record["institution_code"] != source or record["date_precision"] != "day":
        raise ValueError("Voting record differs from requested source/day precision")
    day = date.fromisoformat(record["occurred_on"])
    if not start <= day <= end:
        raise ValueError("Voting record is outside the requested interval")
    return day.isoformat()


def prepare_retirements(items, source, start, end, index):
    if len(items) > 1000:
        raise ValueError("Retirement budget exceeded")
    changes = {}
    for item in items:
        day = date.fromisoformat(item["occurred_on"])
        if not start <= day <= end:
            raise ValueError("Retirement outside acquired interval")
        changed = index.inspect_retirement(source, item)
        if changed is not None:
            changes[(item["occurred_on"], item["voting_id"])] = changed
    return changes


def consolidate_acquisition(result, source, start, end, repository, temporary, storage=None):
    index = VotingChangeIndex(
        repository
        / "private"
        / ("crawler-changes-storage.sqlite" if storage else "crawler-changes-local.sqlite"),
        parser_version=result["parser_version"],
    )
    try:
        files, facts, moved = prepare_daily_changes(
            result["input_path"], source, start, end, temporary, index
        )
        retired = prepare_retirements(
            result.get("explicit_secret_votings", []), source, start, end, index
        )
        removals = {key: value[3] for key, value in retired.items()} | moved
        manifests = activate_daily_partitions(
            files, removals, source, result["parser_version"], repository, temporary, storage
        )
        index.commit_changes(facts, retired.values())
        return {
            "pipeline_triggered": bool(files or removals),
            "changed_facts": len(facts),
            "partitions": len(manifests),
            "rows": sum(m.row_count for m in manifests),
            "published": storage is not None and bool(manifests),
        }
    finally:
        index.close()


def activate_daily_partitions(files, retirements, source, parser, repository, temporary, storage):
    manifests = []
    days = set(files) | {key[0] for key in retirements}
    for day in sorted(days):
        incoming = files.get(day)
        if incoming is None:
            incoming = temporary / (day + ".ndjson")
            incoming.touch(mode=0o600)
        partition = DailyVotingPartition(source, date.fromisoformat(day))
        withdrawals = {key[1]: observed for key, observed in retirements.items() if key[0] == day}
        manifest = consolidate_daily_votes(incoming, repository, partition, parser)
        for voting_id, observed in withdrawals.items():
            manifest = consolidate_daily_votes(
                incoming,
                repository,
                partition,
                parser,
                retired_voting_ids=(voting_id,),
                retirement_observed_at=observed,
            )
        if storage is not None:
            storage.publish_daily_manifest(
                repository / partition.relative_path, partition.relative_path, manifest
            )
        manifests.append(manifest)
    return manifests
