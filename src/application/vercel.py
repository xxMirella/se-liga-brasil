"""WSGI transport for the public portal on Vercel's Python runtime."""

from http import HTTPStatus
from pathlib import Path
from tempfile import gettempdir
from threading import Lock

from application.public_cache import prepare_public_response
from application.public_portal import (
    PublicPortalApplication,
    dispatch_portal_request,
    encode_response,
)
from service.public_profile import PublicProfileError

CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https:; "
    "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
)


def create_dataset_reader():
    import httpx

    from service.dataset_storage.read import DailyDatasetReader
    from service.dataset_storage.supabase import SupabaseDatasetStorage, load_storage_configuration

    configuration = load_storage_configuration()
    client = httpx.Client(timeout=20, follow_redirects=False)
    storage = SupabaseDatasetStorage(configuration, client)
    return DailyDatasetReader(storage, Path(gettempdir()) / "se-liga-brasil-public-cache")


class ServerlessPortalApplication(PublicPortalApplication):
    def __init__(self):
        super().__init__(None, None)
        self.reader_lock = Lock()

    def fetch_votes(self, person_id, parameters):
        # Static pages and PostgreSQL profiles work without Storage credentials.
        with self.reader_lock:
            if self.dataset_reader is None:
                try:
                    self.dataset_reader = create_dataset_reader()
                except (ValueError, OSError) as error:
                    raise PublicProfileError("TEMPORARILY_UNAVAILABLE", 503) from error
        return super().fetch_votes(person_id, parameters)


def request_target(environ):
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    return path + ("?" + query if query else "")


class PublicPortalWSGI:
    def __init__(self, portal=None):
        self.portal = portal if portal is not None else ServerlessPortalApplication()

    def __call__(self, environ, start_response):
        target = request_target(environ)
        method = environ.get("REQUEST_METHOD", "GET")
        response = (
            dispatch_portal_request(self.portal, target)
            if method in {"GET", "HEAD"}
            else encode_response({"error": "METHOD_NOT_ALLOWED"}, status=405)
        )
        status, body, cache_headers = prepare_public_response(
            target,
            response.status,
            response.body,
            {
                "Accept-Encoding": environ.get("HTTP_ACCEPT_ENCODING", ""),
                "If-None-Match": environ.get("HTTP_IF_NONE_MATCH", ""),
            },
            getattr(response, "dataset_version", None),
        )
        headers = {
            **cache_headers,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": CONTENT_SECURITY_POLICY,
        }
        if status != 304:
            headers["Content-Type"] = response.content_type
            headers["Content-Length"] = str(len(body))
        if status == 405:
            headers["Allow"] = "GET, HEAD"
        start_response(f"{status} {HTTPStatus(status).phrase}", list(headers.items()))
        return [] if method == "HEAD" or status == 304 else [body]
