"""Process-wide per-host pacing and bounded interpretation of Retry-After."""

import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import Lock
from urllib.parse import urlsplit

NEXT_REQUEST_AT = {}
PACING_LOCK = Lock()


def pace_official_request(url, interval_seconds=1.0) -> None:
    host = urlsplit(url).hostname
    with PACING_LOCK:
        now = time.monotonic()
        delay = max(0.0, NEXT_REQUEST_AT.get(host, now) - now)
        NEXT_REQUEST_AT[host] = now + delay + interval_seconds
    if delay:
        time.sleep(delay)


def retry_after_seconds(value, now=None) -> float:
    if not value:
        return 0.0
    if value.strip().isdigit():
        return float(value.strip())
    try:
        timestamp = parsedate_to_datetime(value)
        return max(0.0, (timestamp - (now or datetime.now(UTC))).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return 0.0


SOURCE_COOLDOWNS = {}


def postpone_official_host(url, seconds, status) -> None:
    host = urlsplit(url).hostname
    with PACING_LOCK:
        previous = SOURCE_COOLDOWNS.get(host, (0, status))[0]
        SOURCE_COOLDOWNS[host] = (max(previous, time.monotonic() + max(60, seconds)), status)


def enforce_official_cooldown(url) -> None:
    from service.ingestion.contracts import IngestionError

    deadline, status = SOURCE_COOLDOWNS.get(urlsplit(url).hostname, (0, None))
    remaining = deadline - time.monotonic()
    if remaining > 0:
        raise IngestionError(
            "SOURCE_COOLDOWN_ACTIVE", {"status": status, "retry_after_seconds": remaining}
        )
