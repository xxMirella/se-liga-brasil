"""Shared trigger for the annual build scripts: rebuild the serving datasets after a write.

The majority panorama document is derived from the annual dashboard partitions, so it must be
regenerated after them. The rebuild opens its own connection so it always runs after the build
transaction has committed, only when the script confirmed a write (never on a dry run), and a
failure here is logged but never fails the build: only the registry isolates dataset failures.
"""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402
from service.serving import rebuild_serving_datasets  # noqa: E402

logger = logging.getLogger(__name__)


def rebuild_serving_after_write(env_file: Path | None, *, written: bool) -> dict[str, str] | None:
    """{dataset: version or failed:<Error>}; None when nothing was written or the rebuild failed."""
    if not written:
        return None
    try:
        with connect_database(env_file) as connection:
            return rebuild_serving_datasets(connection, datetime.now(UTC).date())
    except Exception:
        logger.exception("serving rebuild skipped; datasets keep their previous release")
        return None
