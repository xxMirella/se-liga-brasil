"""Local read-only HTTP transport; domain queries never acquire source data."""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from application.public_cache import prepare_public_response
from service.public_profile import PublicProfileError

VOTE_QUERY_PARAMETERS = frozenset(
    {"start_date", "end_date", "office_kind", "exercise_id", "cursor", "limit"}
)


def parse_vote_request(target):
    if len(target) > 4096:
        raise ValueError("Request target too long")
    parsed = urlsplit(target)
    match = re.fullmatch(r"/api/people/([0-9a-fA-F-]{36})/votes", parsed.path)
    if match is None or parsed.scheme or parsed.netloc or parsed.fragment:
        return None
    parameters = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=6)
    if set(parameters) - VOTE_QUERY_PARAMETERS or any(len(x) != 1 for x in parameters.values()):
        raise ValueError("Invalid query parameters")
    return match[1], {key: values[0] for key, values in parameters.items()}


def dispatch_public_request(fetch_votes, target):
    try:
        request = parse_vote_request(target)
        if request is None:
            return 404, {"error": "route_not_found"}
        return 200, fetch_votes(*request)
    except PublicProfileError as error:
        return error.status_code, {"error": error.code}
    except ValueError:
        return 400, {"error": "invalid_request"}
    except LookupError:
        return 404, {"error": "person_not_found"}
    except Exception:
        return 503, {"error": "temporarily_unavailable"}


class PublicHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def do_GET(self):
        if self.application is not None:
            from application.public_portal import dispatch_portal_request

            response = dispatch_portal_request(self.application, self.path)
            self.send_content(response.status, response.body, response.content_type)
            return
        status, response = dispatch_public_request(self.fetch_votes, self.path)
        self.send_json(status, response)

    def do_POST(self):
        self.send_json(405, {"error": "method_not_allowed"})

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_content(status, body, "application/json; charset=utf-8")

    def send_content(self, status, body, content_type):
        status, body, headers = prepare_public_response(self.path, status, body, self.headers)
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Type", content_type)
        if status != 304:
            self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https:; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        if status != 304:
            self.wfile.write(body)

    def log_message(self, *_arguments):
        pass


def create_public_handler(fetch_votes, *, application=None):
    return type(
        "ConfiguredPublicHandler",
        (PublicHandler,),
        {"fetch_votes": staticmethod(fetch_votes), "application": application},
    )


def serve_public_api(fetch_votes, *, host="127.0.0.1", port=8779, application=None):
    if host not in {"127.0.0.1", "localhost"} or not 1 <= port <= 65535:
        raise ValueError("Select a loopback host and a valid port")
    with ThreadingHTTPServer(
        (host, port), create_public_handler(fetch_votes, application=application)
    ) as server:
        server.serve_forever(poll_interval=0.5)


def build_vote_query(person_id, parameters):
    from datetime import date

    from service.public_profile import VoteQuery

    if not parameters.get("start_date") or not parameters.get("end_date"):
        raise PublicProfileError("EXPLICIT_PERIOD_REQUIRED")
    return VoteQuery(
        person_id=person_id,
        start_on=date.fromisoformat(parameters["start_date"]),
        end_on=date.fromisoformat(parameters["end_date"]),
        office_kind=parameters.get("office_kind"),
        exercise_id=int(parameters["exercise_id"]) if "exercise_id" in parameters else None,
        cursor=parameters.get("cursor"),
        limit=int(parameters.get("limit", "30")),
    )


def fetch_database_votes(env_file, person_id, parameters):
    from database.operations import connect_database
    from database.public_profile import PublicProfileRepository
    from service.public_profile import get_person_votes

    query = build_vote_query(person_id, parameters)
    with connect_database(env_file) as connection:
        return get_person_votes(PublicProfileRepository(connection), query)


def execute_public_api_command(arguments):
    import httpx

    from application.public_portal import PublicPortalApplication
    from database.operations import PROJECT_ROOT
    from service.dataset_storage.read import DailyDatasetReader
    from service.dataset_storage.supabase import SupabaseDatasetStorage, load_storage_configuration

    configuration = load_storage_configuration(arguments.env_file)
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        storage = SupabaseDatasetStorage(configuration, client)
        reader = DailyDatasetReader(storage, PROJECT_ROOT / "data/public-cache")
        application = PublicPortalApplication(arguments.env_file, reader)
        serve_public_api(None, host=arguments.host, port=arguments.port, application=application)
    return {"status": "stopped"}
