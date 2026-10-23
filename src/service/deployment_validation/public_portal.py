"""Fail builds when the configured application cannot serve actual people searches."""

import json
import os
import re
from wsgiref.util import setup_testing_defaults

from application.vercel import PublicPortalWSGI
from service.dataset_storage.supabase import storage_configuration_from_values


class DeploymentValidationError(ValueError):
    """Only a fixed diagnostic code may be written to a build log."""


def validate_storage_configuration():
    try:
        storage_configuration_from_values(os.environ)
    except ValueError as error:
        raise DeploymentValidationError("SUPABASE_STORAGE_CONFIGURATION_REQUIRED") from error


def check_public_deployment(application=None):
    validate_database_configuration()
    validate_storage_configuration()
    application = application if application is not None else PublicPortalWSGI()
    search = check_public_search(application)
    activity = check_public_activity(application)
    return {"status": "passed", "checks": search["checks"] + activity}


def check_public_activity(application):
    sample = probe_wsgi(application, "/api/people", "limit=1")
    if sample["status"] != 200:
        raise DeploymentValidationError(f"PUBLIC_PEOPLE_HTTP_{sample['status']}")
    people = json.loads(sample["body"])["items"]
    if not people:
        raise DeploymentValidationError("PUBLIC_ACTIVITY_SAMPLE_PERSON_REQUIRED")
    person_id = people[0]["person_id"]
    checks = []
    for path, query in (
        (f"/pessoas/{person_id}", "tab=activity&scope=history"),
        (f"/api/people/{person_id}/votes", "scope=history"),
    ):
        result = probe_wsgi(application, path, query)
        if result["status"] != 200:
            raise DeploymentValidationError(f"PUBLIC_ACTIVITY_HTTP_{result['status']}")
        checks.append({"path": path, "query": query, "status": result["status"]})
    return checks


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
        response["body"] = b"".join(body)
    finally:
        if hasattr(body, "close"):
            body.close()
    return response
