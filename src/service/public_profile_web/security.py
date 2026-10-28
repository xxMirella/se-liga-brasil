"""Escape presentation values and accept only public official HTTPS destinations."""

from html import escape
from urllib.parse import urlencode, urlsplit
from uuid import UUID

OFFICIAL_SOURCE_HOSTS = frozenset({
    "www.defensoria.rj.def.br", "agenciabrasil.ebc.com.br", "prefeitura.rio",
    "neamp.pucsp.br", "repositorio.unb.br", "psd.org.br",
    "files.ufgd.edu.br", "periodicos.fclar.unesp.br",
    "progressistas.org.br", "uniaobrasil.org.br", "albalegis.nopapercloud.com.br",
})


def text(value, fallback="Não disponível"):
    return escape(str(value), quote=True) if value is not None and value != "" else fallback


def official_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port
            or not (hostname.endswith((".leg.br", ".gov.br", ".jus.br"))
                    or hostname in OFFICIAL_SOURCE_HOSTS)
        ):
            return None
    except ValueError:
        return None
    return value


def person_path(person_id):
    return "/pessoas/" + str(UUID(str(person_id)))


def query_link(path, parameters):
    allowed = {
        "tab",
        "scope",
        "q",
        "start_date",
        "end_date",
        "office_kind",
        "uf",
        "political_party",
        "exercise_id",
        "cursor",
        "limit",
    }
    query = urlencode({key: value for key, value in parameters.items() if key in allowed and value})
    return text(path + ("?" + query if query else ""))
