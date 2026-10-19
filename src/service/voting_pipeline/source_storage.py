"""Atomic private source inputs, reusable across official institutions."""

import json
from datetime import datetime
from pathlib import Path

from service.ingestion.contracts import IngestionError
from storage.files import hash_file, save_json, write_private_bytes


def latest_source_observation(*timestamps):
    observations = [datetime.fromisoformat(value) for value in timestamps if value]
    if not observations or any(value.tzinfo is None for value in observations):
        raise IngestionError("SOURCE_OBSERVATION_TIMEZONE_REQUIRED")
    return max(observations).isoformat()


def bounded_input_chunks(rows, maximum_bytes=64 * 1024 * 1024):
    used = 0
    for number, row in enumerate(rows, 1):
        encoded = json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        used += len(encoded) + 1
        if used > maximum_bytes or number > 100000:
            raise IngestionError("VOTING_ANALYTICAL_INPUT_LIMIT_EXCEEDED")
        yield encoded + b"\n"


def write_source_daily_input(
    output_path, rows, receipts, *, parser_version, evidence_dependencies=(), secret_votings=()
):
    path = Path(output_path)
    write_private_bytes(path, bounded_input_chunks(rows))
    metadata = {
        "parser_version": parser_version,
        "input_sha256": hash_file(path),
        "evidence_dependencies": sorted(set(evidence_dependencies)),
        "explicit_secret_voting_keys": sorted({item["voting_id"] for item in secret_votings}),
        "explicit_secret_votings": sorted(secret_votings, key=lambda item: item["voting_id"]),
        "rows": len(rows),
        "receipts": receipts,
        "collection_complete": False,
    }
    save_json(path.with_suffix(path.suffix + ".manifest.json"), metadata)
    return metadata | {"input_path": str(path)}
