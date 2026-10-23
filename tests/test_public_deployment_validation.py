"""Release checks cover the database-backed result page, not just its static shell."""

import json
from unittest.mock import Mock

import pytest

from application.public_portal import PublicPortalApplication
from application.vercel import PublicPortalWSGI
from service.deployment_validation.public_portal import (
    DeploymentValidationError,
    check_public_search,
    probe_wsgi,
)


@pytest.mark.parametrize("value", [None, "", "https://project.supabase.co"])
def test_missing_postgres_configuration_blocks_release_before_application_call(monkeypatch, value):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    if value is not None:
        monkeypatch.setenv("DATABASE_URL", value)
    application = Mock(side_effect=AssertionError("A release without database config must fail"))
    with pytest.raises(DeploymentValidationError, match="POSTGRES_CONNECTION_REQUIRED"):
        check_public_search(application)
    application.assert_not_called()


def test_shell_success_cannot_hide_missing_database_configuration(monkeypatch, caplog):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    application = PublicPortalWSGI(PublicPortalApplication(None, None))
    assert probe_wsgi(application, "/pessoas", "")["status"] == 200
    assert probe_wsgi(application, "/pessoas", "limit=4")["status"] == 503
    with pytest.raises(DeploymentValidationError, match="POSTGRES_CONNECTION_REQUIRED"):
        check_public_search(application)
    assert "error_type=IngestionError" in caplog.text


def test_release_probes_both_rendered_results_and_filtered_json(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci:ci@localhost/test")
    observed = []

    def available(environ, start_response):
        observed.append((environ["PATH_INFO"], environ["QUERY_STRING"]))
        start_response("200 OK", [])
        return [b"public result"]

    assert check_public_search(available)["status"] == "passed"
    assert observed == [
        ("/pessoas", "limit=4"), ("/api/people", "limit=4"),
        ("/api/people", "q=Brasil&limit=4"),
    ]


def test_database_failure_blocks_deploy_and_never_logs_exception_message(monkeypatch, caplog):
    from database import operations

    secret = "private-database-password"
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci:ci@localhost/test")
    monkeypatch.setattr(operations, "connect_database", Mock(side_effect=OSError(secret)))
    with pytest.raises(DeploymentValidationError, match="PUBLIC_PEOPLE_HTTP_503"):
        check_public_search()
    assert secret not in caplog.text
    assert "error_type=OSError" in caplog.text


def test_vercel_build_runs_public_search_check():
    from database.operations import PROJECT_ROOT

    configuration = json.loads((PROJECT_ROOT / "vercel.json").read_text())
    assert configuration["buildCommand"] == "python scripts/check_public_deployment.py"


def test_favicon_is_local_svg_available_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    application = PublicPortalWSGI()
    assert probe_wsgi(application, "/assets/brazil-flag.svg", "")["status"] == 200
    assert probe_wsgi(application, "/favicon.ico", "")["status"] == 200
