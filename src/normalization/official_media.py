"""Normalize HTTPS media links for explicitly trusted institutional hosts."""

from urllib.parse import urlsplit, urlunsplit


def normalize_official_media_url(value, allowed_hosts, *, upgrade_http=False):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
            return None
        if parsed.port not in (None, 443) or parsed.fragment or not parsed.path:
            return None
        if parsed.scheme == "https":
            return value
        if parsed.scheme == "http" and upgrade_http:
            return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    except ValueError:
        return None
    return None
