"""Adapter: feeds the majority panorama builder from the dashboard's own annual data.

One dashboard read for the current year carries the annual history of every year (composition per
house, presidential segments). Presidential names come from one extra read per term start year
(at most nine). The reads go through the dashboard cache; the caller caches the finished panorama.
"""

from service.majority_panorama.builder import build_majority_panorama
from service.majority_panorama.presidents import (
    FIRST_TERM_START,
    collect_presidential_exercises,
)


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
                    "name": segment.get("name"), "official_url": segment.get("official_url"),
                }
        return identities

    def presidency(self):
        segments_by_year = self.segments_by_year()
        return collect_presidential_exercises(
            segments_by_year, self.identities(segments_by_year)
        )


class MajorityPanoramaReader:
    def __init__(self, fetch_dashboard, today):
        self.fetch_dashboard, self.today = fetch_dashboard, today

    def fetch(self):
        today = self.today()
        return build_majority_panorama(DashboardPanoramaSource(self.fetch_dashboard, today), today)


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
        with self._lock:
            if self._value is None or self.clock() >= self._expires_at:
                self._value = self.reader.fetch()
                self._expires_at = self.clock() + self.ttl_seconds
            return self._value
