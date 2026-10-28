"""Content-addressed annual JSON payloads; activation is a separate transaction."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

MAX_PARTITION_BYTES = 256 * 1024


def encode_partition(partition):
    content = json.dumps(
        partition, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    if len(content) > MAX_PARTITION_BYTES:
        raise ValueError("ANNUAL_PARTITION_PAYLOAD_BUDGET_EXCEEDED")
    return content, hashlib.sha256(content).hexdigest()


def store_partition(directory, partition):
    content, digest = encode_partition(partition)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (digest + ".json")
    write_atomic(destination, content)
    return {
        "year": partition["year"],
        "territory_code": partition["territory_code"],
        "institution_code": partition["institution_code"],
        "sha256": digest,
        "bytes": len(content),
        "file": destination.name,
    }


def write_atomic(destination, content):
    destination = Path(destination)
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=directory, delete=False) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
