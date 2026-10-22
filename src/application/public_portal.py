"""Compose public HTML and JSON over read-only metadata and published datasets."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from service.public_profile import PublicProfileError

SEARCH_PARAMETERS = frozenset({"q", "uf", "office_kind", "political_party", "cursor", "limit"})
PROFILE_PARAMETERS = frozenset(
    {
        "tab",
        "scope",
        "start_date",
        "end_date",
        "office_kind",
        "exercise_id",
        "cursor",
        "limit",
        "proposal_page",
    }
)
PERSON_ROUTE = re.compile(r"/(api/people|pessoas)/([0-9a-fA-F-]{36})(/votes)?")


@dataclass(frozen=True)
class PublicResponse:
    status: int
    body: bytes
    content_type: str


def encode_response(payload, *, status=200, content_type="application/json"):
    if content_type == "application/json":
        payload = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return PublicResponse(status, payload.encode("utf-8"), content_type + "; charset=utf-8")


def read_parameters(query, allowed):
    values = parse_qs(query, keep_blank_values=True, max_num_fields=len(allowed))
    if set(values) - allowed or any(len(items) != 1 for items in values.values()):
        raise PublicProfileError("INVALID_QUERY_PARAMETERS")
    return {key: items[0] for key, items in values.items() if items[0] != ""}


def dispatch_portal_request(application, target):
    try:
        if len(target) > 4096:
            raise PublicProfileError("REQUEST_TARGET_TOO_LONG")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            return encode_response({"error": "ROUTE_NOT_FOUND"}, status=404)
        return route_public_request(application, parsed)
    except PublicProfileError as error:
        return encode_public_error(target, error.code, error.status_code)
    except ValueError:
        return encode_public_error(target, "INVALID_REQUEST", 400)
    except Exception:
        return encode_public_error(target, "TEMPORARILY_UNAVAILABLE", 503)


def encode_public_error(target, code, status):
    if (
        target.startswith(("/pessoas", "/como-funciona", "/sobre"))
        or target.partition("?")[0] == "/"
    ):
        from service.public_profile_web import render_error_page

        messages = {
            400: "Confira os filtros. A consulta de votos aceita até 31 dias por vez.",
            404: "A pessoa ou o exercício solicitado não está disponível.",
            410: "Esta página expirou. Reinicie a consulta para carregar os dados publicados.",
        }
        message = messages.get(status, "A consulta está temporariamente indisponível.")
        return encode_response(
            render_error_page(status, message), status=status, content_type="text/html"
        )
    return encode_response({"error": code}, status=status)


def route_public_request(application, parsed):
    educational_response = route_education_request(parsed)
    if educational_response is not None:
        return educational_response
    if parsed.path in {"/pessoas", "/api/people"}:
        parameters = read_parameters(parsed.query, SEARCH_PARAMETERS)
        if parsed.path == "/pessoas" and "limit" not in parameters:
            from service.public_profile.people_contracts import PeopleQuery
            from service.public_profile_web.search import render_search_shell

            PeopleQuery(**parameters)
            return encode_response(render_search_shell(parameters), content_type="text/html")
        result = application.fetch_people(parameters)
        if parsed.path == "/api/people":
            return encode_response(result)
        from service.public_profile_web import render_search_page

        return encode_response(render_search_page(parameters, result), content_type="text/html")
    if parsed.path == "/assets/people-viewport.js" and not parsed.query:
        from pathlib import Path

        import service.public_profile_web.search as search_module

        script = Path(search_module.__file__).parent / "assets" / "people-viewport.js"
        return encode_response(script.read_text(encoding="utf-8"), content_type="text/javascript")
    if parsed.path == "/assets/public-profile.css" and not parsed.query:
        from service.public_profile_web import public_stylesheet

        return encode_response(public_stylesheet(), content_type="text/css")
    match = PERSON_ROUTE.fullmatch(parsed.path)
    if match:
        return route_person_request(application, match, parsed.query)
    return encode_response({"error": "ROUTE_NOT_FOUND"}, status=404)


def route_education_request(parsed):
    if parsed.path in {"/", "/sobre", "/sobre/"}:
        from service.project_information.page import render_project_information

        read_parameters(parsed.query, set())
        return encode_response(render_project_information(), content_type="text/html")
    if parsed.path == "/como-funciona":
        from service.civic_education.page import render_civic_education

        parameters = read_parameters(parsed.query, {"esfera"})
        return encode_response(
            render_civic_education(parameters.get("esfera", "municipal")), content_type="text/html"
        )
    if parsed.path == "/assets/civic-education.css" and not parsed.query:
        from service.civic_education.page import civic_stylesheet

        return encode_response(civic_stylesheet(), content_type="text/css")
    return None


def route_person_request(application, match, query):
    surface, person_id, suffix = match.groups()
    if surface == "api/people":
        if suffix:
            allowed = PROFILE_PARAMETERS - {"tab", "proposal_page"}
            return encode_response(
                application.fetch_votes(person_id, read_parameters(query, allowed))
            )
        if query:
            raise PublicProfileError("UNEXPECTED_PROFILE_PARAMETERS")
        return encode_response(application.fetch_person(person_id))
    if suffix:
        return encode_response({"error": "ROUTE_NOT_FOUND"}, status=404)
    from service.public_profile_web import render_person_profile

    parameters = read_parameters(query, PROFILE_PARAMETERS)
    if "proposal_page" in parameters and not 1 <= int(parameters["proposal_page"]) <= 1000:
        raise PublicProfileError("INVALID_PROPOSITION_PAGE")
    filters = application.profile_filters(parameters)
    profile = (
        application.fetch_person(person_id, proposal_page=int(parameters["proposal_page"]))
        if "proposal_page" in parameters
        else application.fetch_person(person_id)
    )
    votes = {"items": [], "coverage": {"state": "not_requested"}}
    if filters["tab"] == "activity":
        votes = application.fetch_votes(
            person_id, {k: v for k, v in filters.items() if k not in {"tab", "proposal_page"}}
        )
    return encode_response(render_person_profile(profile, votes, filters), content_type="text/html")


class PublicPortalApplication:
    def __init__(self, env_file, dataset_reader, *, today=None):
        self.env_file, self.dataset_reader = env_file, dataset_reader
        from service.public_profile.search_cache import PublicSearchCache

        self.people_cache = PublicSearchCache()
        self.today = today or (lambda: datetime.now(ZoneInfo("America/Belem")).date())

    def fetch_people(self, parameters):
        from database.operations import connect_database
        from database.public_people import PublicPeopleRepository
        from service.public_profile.people import search_people
        from service.public_profile.people_contracts import PeopleQuery

        query = PeopleQuery(
            q=parameters.get("q", ""),
            uf=parameters.get("uf"),
            office_kind=parameters.get("office_kind"),
            political_party=parameters.get("political_party"),
            cursor=parameters.get("cursor"),
            limit=int(parameters.get("limit", "6")),
        )
        as_of = self.today()
        from service.public_profile.people_contracts import decode_people_cursor

        decode_people_cursor(query, as_of)

        def load_public_people():
            with connect_database(self.env_file) as connection:
                return search_people(PublicPeopleRepository(connection), query, as_of)

        return self.people_cache.get_or_load((query, as_of), load_public_people)

    def fetch_person(self, person_id, *, proposal_page=1):
        from database.attendance import (
            fetch_person_attendance,
            fetch_person_attendance_history,
        )
        from database.cabinet_payroll import fetch_cabinet_payroll_history
        from database.office_legal_scopes import fetch_public_office_scopes
        from database.operations import connect_database
        from database.public_assets import PublicAssetsRepository
        from database.public_people import PublicPeopleRepository
        from database.public_propositions import fetch_person_propositions
        from service.cabinet_payroll.public_projection import public_cabinet_payroll
        from service.public_profile.assets import get_public_assets
        from service.public_profile.people import get_public_person

        as_of = self.today()
        with connect_database(self.env_file) as connection:
            repository = PublicPeopleRepository(connection)
            profile = get_public_person(repository, person_id, as_of)
            profile["assets"] = get_public_assets(
                PublicAssetsRepository(connection), person_id, as_of
            )
            with repository.read_snapshot():
                profile["attendance"] = fetch_person_attendance(connection, person_id, as_of)
                profile["propositions"] = fetch_person_propositions(
                    connection, person_id, as_of, proposal_page
                )
                profile["attendance_history"] = fetch_person_attendance_history(
                    connection, person_id, as_of
                )
                profile["legal_scopes"] = fetch_public_office_scopes(connection, person_id, as_of)
                profile["cabinet_payroll"] = public_cabinet_payroll(
                    fetch_cabinet_payroll_history(connection, person_id, as_of)
                )
            return profile

    def fetch_votes(self, person_id, parameters):
        from application.public_api import build_vote_query
        from database.operations import connect_database
        from database.public_profile import PublicProfileRepository
        from service.public_profile.storage_votes import get_person_storage_votes

        if parameters.get("scope", "period") not in {"history", "period"}:
            raise PublicProfileError("INVALID_TIMELINE_SCOPE")
        if parameters.get("scope") == "history":
            return self.fetch_history(person_id, parameters)
        parameters = {key: value for key, value in parameters.items() if key != "scope"}
        query = build_vote_query(person_id, parameters)
        with connect_database(self.env_file) as connection:
            return get_person_storage_votes(
                PublicProfileRepository(connection), self.dataset_reader, query
            )

    def fetch_history(self, person_id, parameters):
        from database.operations import connect_database
        from database.public_profile import PublicProfileRepository
        from service.public_profile.storage_history import get_person_storage_history

        with connect_database(self.env_file) as connection:
            return get_person_storage_history(
                PublicProfileRepository(connection),
                self.dataset_reader,
                person_id,
                office_kind=parameters.get("office_kind"),
                exercise_id=int(parameters["exercise_id"])
                if parameters.get("exercise_id")
                else None,
                cursor=parameters.get("cursor"),
                limit=int(parameters.get("limit", "30")),
                as_of=self.today(),
            )

    def profile_filters(self, parameters):
        result = {
            "tab": "profile",
            "start_date": str(self.today() - timedelta(days=29)),
            "end_date": str(self.today()),
            **parameters,
        }
        result.setdefault(
            "scope", "history" if not {"start_date", "end_date"} & parameters.keys() else "period"
        )
        if result["scope"] not in {"history", "period"}:
            raise PublicProfileError("INVALID_TIMELINE_SCOPE")
        if result["scope"] == "history":
            result["start_date"] = ""
            result["end_date"] = ""
        if result["tab"] not in {"profile", "activity"}:
            raise PublicProfileError("INVALID_PROFILE_TAB")
        return result
