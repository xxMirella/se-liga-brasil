"""Atomic, private local storage and streaming content fingerprints."""

import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

CHUNK_BYTES = 1024 * 1024


def hash_content(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)


def write_private_bytes(path: Path, chunks: Iterable[bytes]) -> None:
    create_private_directory(path.parent)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.part")
    try:
        with temporary.open("xb") as output:
            temporary.chmod(0o600)
            for chunk in chunks:
                output.write(chunk)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_json(path: Path, value: Any) -> None:
    write_private_bytes(path, [json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")])


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_lines(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def write_json_line(output: Any, record: dict[str, Any]) -> None:
    output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
