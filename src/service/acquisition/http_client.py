"""Restricted official-source HTTP transport with bounded retries."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urljoin, urlsplit

import httpx

from service.acquisition.rate_limit import (
    enforce_official_cooldown,
    pace_official_request,
    postpone_official_host,
    retry_after_seconds,
)
from service.ingestion.contracts import IngestionError

MAX_REDIRECTS = 5
MAX_CATALOG_BYTES = 10 * 1024**2
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def validate_official_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urlsplit(url)
    trusted = parsed.scheme == "https" and parsed.hostname in allowed_hosts
    if not trusted or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise IngestionError("UNTRUSTED_RESOURCE_URL")


class OfficialHttpClient:
    def __init__(self, configuration, client: httpx.Client, allowed_hosts: frozenset[str]) -> None:
        self.configuration = configuration
        self.client = client
        self.allowed_hosts = allowed_hosts

    @contextmanager
    def stream_response(self, url: str, headers: dict | None = None) -> Iterator[httpx.Response]:
        response = self._open_response(url, headers or {})
        try:
            yield response
        finally:
            response.close()

    def _open_response(self, url: str, headers: dict) -> httpx.Response:
        for attempt in range(self.configuration.max_attempts):
            try:
                return self._follow_official_redirects(url, headers)
            except (httpx.TransportError, IngestionError) as error:
                delay = retry_delay(error, attempt, self.configuration.max_attempts, url)
                if delay is None:
                    raise
                time.sleep(delay)
        raise IngestionError("HTTP_ATTEMPTS_EXHAUSTED")

    def _follow_official_redirects(self, url: str, headers: dict) -> httpx.Response:
        for _ in range(MAX_REDIRECTS + 1):
            validate_official_url(url, self.allowed_hosts)
            enforce_official_cooldown(url)
            request = self.client.build_request("GET", url, headers=headers)
            pace_official_request(
                url, getattr(self.configuration, "request_min_interval_seconds", 1.0)
            )
            response = self.client.send(request, stream=True, follow_redirects=False)
            if response.status_code in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.headers.get("location", ""))
                response.close()
                continue
            if response.status_code == 304 or response.is_success:
                return response
            retry_after = retry_after_seconds(response.headers.get("Retry-After"))
            if response.status_code in {403, 429}:
                postpone_official_host(url, max(3600, retry_after), response.status_code)
            response.close()
            raise IngestionError(
                "HTTP_ERROR",
                {
                    "status": response.status_code,
                    "retryable": response.status_code in RETRYABLE_STATUSES
                    and response.status_code != 429,
                    "retry_after_seconds": retry_after,
                },
            )
        raise IngestionError("TOO_MANY_REDIRECTS")

    def fetch_bytes(self, url: str, max_bytes: int = MAX_CATALOG_BYTES) -> bytes:
        with self.stream_response(url) as response:
            chunks = []
            byte_count = 0
            for chunk in response.iter_bytes():
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise IngestionError("RESOURCE_DOWNLOAD_LIMIT_EXCEEDED")
                chunks.append(chunk)
        return b"".join(chunks)


def retry_delay(error, attempt, attempts, url) -> float | None:
    details = error.details if isinstance(error, IngestionError) else {}
    retryable = isinstance(error, httpx.TransportError) or details.get("retryable")
    if not retryable or attempt + 1 == attempts:
        if details.get("status") in {500, 502, 503, 504}:
            postpone_official_host(
                url, max(60, details.get("retry_after_seconds", 0)), details["status"]
            )
        return None
    delay = max(0.5 * 2**attempt, details.get("retry_after_seconds", 0))
    if delay > 60:
        postpone_official_host(url, delay, details.get("status"))
        return None
    return delay
