"""Fail builds when the configured application cannot serve actual people searches."""

import os
import re
from wsgiref.util import setup_testing_defaults

from application.vercel import PublicPortalWSGI


class DeploymentValidationError(ValueError):
    """Only a fixed diagnostic code may be written to a build log."""


def validate_database_configuration():
    value = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL", "")
    if not re.match(r"^postgres(?:ql)?://", value):
        raise DeploymentValidationError("POSTGRES_CONNECTION_REQUIRED")


def check_public_search(application=None):
    validate_database_configuration()
    application = application if application is not None else PublicPortalWSGI()
    checks = []
    for path, query in (
        ("/pessoas", "limit=4"),
        ("/api/people", "limit=4"),
        ("/api/people", "q=Brasil&limit=4"),
    ):
        response = probe_wsgi(application, path, query)
        if response["status"] != 200:
            raise DeploymentValidationError(f"PUBLIC_PEOPLE_HTTP_{response['status']}")
        checks.append({"path": path, "query": query, "status": response["status"]})
    return {"status": "passed", "checks": checks}


def probe_wsgi(application, path, query):
    environ = {}
    setup_testing_defaults(environ)
    environ.update(PATH_INFO=path, QUERY_STRING=query)
    response = {}

    def capture_status(status, headers):
        response["status"] = int(status.split()[0])

    body = application(environ, capture_status)
    try:
        b"".join(body)
    finally:
        if hasattr(body, "close"):
            body.close()
    return response
