"""Read-only transport hides errors, preserves cache responses and never crawls."""

from contextlib import nullcontext
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application import public_api as api

PERSON = "00000000-0000-0000-0000-000000000001"
TARGET = f"/api/people/{PERSON}/votes"


@pytest.mark.parametrize(
    "target,status", [("/unknown", 404), (TARGET + "?extra=x", 400), (TARGET, 200)]
)
def test_dispatch_route_boundaries(target, status):
    assert api.dispatch_public_request(lambda *_: {"items": []}, target)[0] == status


def test_lookup_failure_is_not_a_server_error():
    assert api.dispatch_public_request(Mock(side_effect=LookupError), TARGET) == (
        404,
        {"error": "person_not_found"},
    )


@pytest.mark.parametrize("port", [0, 65536])
def test_invalid_ports_rejected_before_server_construction(port):
    with pytest.raises(ValueError, match="valid port"):
        api.serve_public_api(None, port=port)


def test_server_composition_closes_transport_when_loop_stops(monkeypatch):
    server = SimpleNamespace(serve_forever=Mock())
    construct = Mock(return_value=nullcontext(server))
    monkeypatch.setattr(api, "ThreadingHTTPServer", construct)
    api.serve_public_api(None, host="localhost", port=8780)
    assert construct.call_args.args[0] == ("localhost", 8780)
    server.serve_forever.assert_called_once_with(poll_interval=0.5)


@pytest.mark.parametrize("status", [200, 304])
def test_not_modified_response_has_no_body_or_content_length(monkeypatch, status):
    monkeypatch.setattr(
        api, "prepare_public_response", lambda *_: (status, b"body", {"ETag": "hash"})
    )
    handler = SimpleNamespace(
        path="/como-funciona",
        headers={},
        wfile=BytesIO(),
        send_response=Mock(),
        send_header=Mock(),
        end_headers=Mock(),
    )
    api.PublicHandler.send_content(handler, 200, b"body", "text/html")
    names = [call.args[0] for call in handler.send_header.call_args_list]
    assert ("Content-Length" in names) == (status != 304)
    assert handler.wfile.getvalue() == (b"body" if status == 200 else b"")
    assert "Content-Security-Policy" in names and "X-Content-Type-Options" in names


def test_post_requests_cannot_modify_public_profiles():
    handler = SimpleNamespace(send_json=Mock())
    api.PublicHandler.do_POST(handler)
    handler.send_json.assert_called_once_with(405, {"error": "method_not_allowed"})


def test_json_response_preserves_unicode_and_rejects_nan():
    handler = SimpleNamespace(send_content=Mock())
    api.PublicHandler.send_json(handler, 200, {"nome": "João"})
    assert "João" in handler.send_content.call_args.args[1].decode()
    with pytest.raises(ValueError):
        api.PublicHandler.send_json(handler, 200, {"number": float("nan")})


@pytest.mark.parametrize("portal", [False, True])
def test_get_uses_only_selected_read_adapter(monkeypatch, portal):
    import application.public_portal as application

    monkeypatch.setattr(
        application,
        "dispatch_portal_request",
        lambda *_: SimpleNamespace(
            status=200,
            body=b"portal",
            content_type="text/html",
        ),
    )
    handler = SimpleNamespace(
        application=object() if portal else None,
        path=TARGET,
        fetch_votes=lambda *_: {"items": []},
        send_content=Mock(),
        send_json=Mock(),
    )
    api.PublicHandler.do_GET(handler)
    assert handler.send_content.call_count == int(portal)
    assert handler.send_json.call_count == int(not portal)
    api.PublicHandler.log_message(handler, "private log ignored")


def test_database_vote_adapter_receives_validated_query(monkeypatch):
    import database.operations as operations
    import database.public_profile as repository
    import service.public_profile as service

    monkeypatch.setattr(operations, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(repository, "PublicProfileRepository", lambda _: "repository")
    get_votes = Mock(return_value={"items": []})
    monkeypatch.setattr(service, "get_person_votes", get_votes)
    assert api.fetch_database_votes(
        None,
        PERSON,
        {
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "exercise_id": "1",
        },
    ) == {"items": []}
    assert get_votes.call_args.args[1].exercise_id == 1


def test_serve_command_uses_private_storage_without_network(monkeypatch):
    import httpx

    import application.public_portal as portal
    import service.dataset_storage.read as reader
    import service.dataset_storage.supabase as storage

    monkeypatch.setattr(httpx, "Client", lambda **_: nullcontext(object()))
    monkeypatch.setattr(storage, "load_storage_configuration", lambda _: object())
    monkeypatch.setattr(storage, "SupabaseDatasetStorage", lambda *_: object())
    monkeypatch.setattr(reader, "DailyDatasetReader", lambda *_: "reader")
    monkeypatch.setattr(portal, "PublicPortalApplication", lambda *_: "application")
    serve = Mock()
    monkeypatch.setattr(api, "serve_public_api", serve)
    assert api.execute_public_api_command(
        SimpleNamespace(env_file=None, host="localhost", port=8780)
    ) == {"status": "stopped"}
    assert serve.call_args.kwargs["application"] == "application"
