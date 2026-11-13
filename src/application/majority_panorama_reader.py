"""Adapter: feeds the majority panorama builder from the dashboard's own annual data.

One dashboard read for the current year carries the annual history of every year (composition per
house, presidential segments). Presidential names come from one extra read per term start year
(at most nine). The reads go through the dashboard cache; the caller caches the finished panorama.
"""

import logging
from dataclasses import dataclass

from service.majority_panorama.builder import build_majority_panorama
from service.majority_panorama.presidents import (
    FIRST_TERM_START,
    collect_presidential_exercises,
)

logger = logging.getLogger(__name__)


class DashboardPanoramaSource:
    def __init__(self, fetch_dashboard, today):
        self.fetch_dashboard, self.today = fetch_dashboard, today
        latest = fetch_dashboard({"year": str(today.year)})
        self.history = {row["year"]: row for row in latest.get("history") or ()}

    def institution(self, code, year):
        for institution in (self.history.get(year) or {}).get("institutions", ()):
            if institution.get("institution_code") == code and (
                institution.get("territory_code") in {None, "BR"}
            ):
                return institution
        return None

    def annual_composition(self, house, year):
        return self.institution(house, year)

    def segments_by_year(self):
        by_year = {}
        for year in self.history:
            presidency = self.institution("presidency", year)
            if presidency and presidency.get("segments"):
                by_year[year] = presidency["segments"]
        return by_year

    def identities(self, segments_by_year):
        """Name and URL of each exercise, read once per start year of a post-1985 exercise."""
        starts = {}
        for segments in segments_by_year.values():
            for segment in segments:
                if segment["starts_on"] >= FIRST_TERM_START.isoformat():
                    starts.setdefault(segment["exercise_id"], int(segment["starts_on"][:4]))
        identities = {}
        for year in sorted(set(starts.values())):
            payload = self.fetch_dashboard({"year": str(year)})
            for segment in (payload.get("presidency") or {}).get("segments", ()):
                identities[segment["exercise_id"]] = segment | {
                    "name": segment.get("name"),
                    "official_url": segment.get("official_url"),
                }
        return identities

    def presidency(self):
        segments_by_year = self.segments_by_year()
        return collect_presidential_exercises(segments_by_year, self.identities(segments_by_year))


@dataclass(frozen=True)
class MajorityPanoramaReading:
    """A panorama and, when it came from the serving registry, the release that produced it.

    `release_version` is None for a live assembly: its only freshness marker is `generated_on`.
    """

    panorama: object
    release_version: str | None = None


class MajorityPanoramaReader:
    """Serves the panorama stored by the serving registry; assembles it live when there is none."""

    def __init__(self, fetch_dashboard, today, read_connections=None):
        self.fetch_dashboard, self.today = fetch_dashboard, today
        self.read_connections = read_connections

    def fetch(self):
        return self.fetch_reading().panorama

    def fetch_reading(self):
        today = self.today()
        return self.fetch_released_reading(today) or MajorityPanoramaReading(self.assemble(today))

    def assemble(self, today):
        return build_majority_panorama(DashboardPanoramaSource(self.fetch_dashboard, today), today)

    def fetch_released(self, today):
        """The released document, or None (no pool, no release, stale, or any read problem)."""
        reading = self.fetch_released_reading(today)
        return None if reading is None else reading.panorama

    def fetch_released_reading(self, today):
        """Like `fetch_released`, with the version of the release the document belongs to."""
        if self.read_connections is None:
            return None
        try:
            return self.read_connections.read(lambda connection: _released(connection, today))
        except Exception:
            logger.exception("panorama document unreadable; assembling live")
            return None


def _released(connection, today):
    from service.majority_panorama.document_codec import decode_exact
    from service.serving.majority_panorama_document import (
        DATASET_NAME,
        read_panorama_document,
    )
    from service.serving.release import current_release

    release = current_release(connection, DATASET_NAME, today)
    if release is None:
        return None
    document = read_panorama_document(connection)
    if document is None:
        return None
    return MajorityPanoramaReading(decode_exact(document), release.version)


class CachedMajorityPanorama:
    """Keeps the finished panorama for a few minutes: building it reads the dashboard ~11 times."""

    def __init__(self, reader, *, ttl_seconds=300, clock=None):
        import threading
        import time

        self.reader, self.ttl_seconds = reader, ttl_seconds
        self.clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._value, self._expires_at = None, 0.0

    def fetch(self):
        return self.fetch_reading().panorama

    def fetch_reading(self):
        with self._lock:
            if self._value is None or self.clock() >= self._expires_at:
                self._value = self.reader.fetch_reading()
                self._expires_at = self.clock() + self.ttl_seconds
            return self._value
