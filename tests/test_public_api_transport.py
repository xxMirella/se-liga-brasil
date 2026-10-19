import pytest

from application.public_api import parse_vote_request, serve_public_api

PERSON = "00000000-0000-0000-0000-000000000001"


def test_route_preserves_explicit_scope_and_cursor():
    assert parse_vote_request(
        f"/api/people/{PERSON}/votes?start_date=2026-01-01&limit=10&cursor=opaque"
    ) == (PERSON, {"start_date": "2026-01-01", "limit": "10", "cursor": "opaque"})


@pytest.mark.parametrize("query", ["limit=1&limit=2", "document=123", "limit=" + "x" * 4096])
def test_ambiguous_unknown_and_oversized_requests_are_rejected(query):
    with pytest.raises(ValueError):
        parse_vote_request(f"/api/people/{PERSON}/votes?{query}")


def test_unknown_routes_are_not_dispatched():
    assert parse_vote_request("/api/private/payroll") is None
    assert parse_vote_request(f"https://example.invalid/api/people/{PERSON}/votes") is None


def test_development_transport_cannot_bind_public_interfaces():
    with pytest.raises(ValueError, match="loopback"):
        serve_public_api(lambda *_: {}, host="0.0.0.0")


def test_http_dispatch_preserves_domain_status_and_hides_private_errors():
    from application.public_api import dispatch_public_request
    from service.public_profile import PublicProfileError

    target = f"/api/people/{PERSON}/votes"

    def missing(*_arguments):
        raise PublicProfileError("PERSON_NOT_FOUND", 404)

    def unavailable(*_arguments):
        raise RuntimeError("private database connection detail")

    assert dispatch_public_request(missing, target) == (404, {"error": "PERSON_NOT_FOUND"})
    assert dispatch_public_request(unavailable, target) == (
        503,
        {"error": "temporarily_unavailable"},
    )


def test_explicit_period_is_required_before_database_connection():
    from application.public_api import fetch_database_votes
    from service.public_profile import PublicProfileError

    with pytest.raises(PublicProfileError, match="EXPLICIT_PERIOD_REQUIRED"):
        fetch_database_votes(None, PERSON, {})


def test_idle_browser_connection_does_not_block_another_request():
    import socket
    from threading import Event

    from application.public_api import ThreadingHTTPServer, create_public_handler

    accepted = Event()
    handler = create_public_handler(lambda *_: {"items": []})

    class ObservedHandler(handler):
        def setup(self):
            super().setup()
            accepted.set()

    # Socket pairs exercise real request handling without a listening port or database.
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), ObservedHandler, bind_and_activate=False
    )
    idle_client, idle_server = socket.socketpair()
    client, request_socket = socket.socketpair()
    try:
        server.process_request(idle_server, ("127.0.0.1", 1))
        assert accepted.wait(1), "The idle connection must be accepted first"
        client.settimeout(1)
        client.sendall(f"GET /api/people/{PERSON}/votes HTTP/1.0\r\n\r\n".encode())
        server.process_request(request_socket, ("127.0.0.1", 2))
        assert client.recv(4096).startswith(b"HTTP/1.0 200")
    finally:
        idle_client.close()
        client.close()
        server.server_close()
