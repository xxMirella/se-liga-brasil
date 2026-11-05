"""Read packaged text assets once per file version instead of once per request."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def _read_versioned_text(path, modified_ns, size):
    return path.read_text(encoding="utf-8")


def read_static_text(path: Path) -> str:
    """Return file text; one stat per call, one read per (mtime, size), so edits are never stale."""
    status = path.stat()
    return _read_versioned_text(path, status.st_mtime_ns, status.st_size)


def clear_static_text_cache() -> None:
    _read_versioned_text.cache_clear()
