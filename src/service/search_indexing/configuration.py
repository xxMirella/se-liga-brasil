"""Explicit public origin; request Host headers never control canonical URLs."""

import os
import re
from urllib.parse import urlsplit

DEFAULT_SITE_ORIGIN = "https://seligabrasil.gov"


def public_site_origin():
    value = (os.environ.get("PUBLIC_SITE_URL") or DEFAULT_SITE_ORIGIN).rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname
            or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", parsed.hostname)
            or parsed.username or parsed.password
            or parsed.port not in {None, 443} or parsed.path or parsed.query or parsed.fragment
            or any(character.isspace() for character in value)):
        raise ValueError("PUBLIC_SITE_URL_MUST_BE_AN_HTTPS_ORIGIN")
    return value


def search_indexing_enabled():
    return (os.environ.get("VERCEL_ENV") not in {"preview", "development"}
            and (os.environ.get("SEARCH_INDEXING_ENABLED") or "true").lower() == "true")
