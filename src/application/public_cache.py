"""HTTP representations for public static content; dynamic data stays uncached."""

import gzip
import hashlib
from functools import lru_cache
from urllib.parse import urlsplit


def public_cache_policy(target, status):
    if status != 200:
        return "no-store"
    path = urlsplit(target).path
    if path in {"/", "/como-funciona", "/sobre", "/sobre/"}:
        return "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
    if path in {
        "/assets/public-profile.css", "/assets/civic-education.css", "/assets/brazil-flag.svg",
        "/favicon.ico",
    }:
        return "public, max-age=0, must-revalidate"
    return "no-store"


def accepts_gzip(header):
    for entry in header.lower().split(","):
        name, *parameters = entry.strip().split(";")
        if name != "gzip":
            continue
        try:
            quality = next((p.strip()[2:] for p in parameters if p.strip().startswith("q=")), "1")
            return 0 < float(quality) <= 1
        except ValueError:
            return False
    return False


@lru_cache(maxsize=32)
def compressed_body(body):
    return gzip.compress(body, compresslevel=6, mtime=0)


def public_representation(body, accept_encoding):
    compressed = len(body) >= 1024 and accepts_gzip(accept_encoding)
    representation = compressed_body(body) if compressed else body
    etag = '"' + hashlib.sha256(representation).hexdigest() + '"'
    return representation, etag, compressed


def matches_etag(header, etag):
    return any(value.strip().removeprefix("W/") in {etag, "*"} for value in header.split(","))


def prepare_public_response(target, status, body, request_headers):
    policy = public_cache_policy(target, status)
    headers = {"Cache-Control": policy}
    if policy == "no-store":
        return status, body, headers
    body, etag, compressed = public_representation(body, request_headers.get("Accept-Encoding", ""))
    headers.update({"ETag": etag, "Vary": "Accept-Encoding"})
    if compressed:
        headers["Content-Encoding"] = "gzip"
    if matches_etag(request_headers.get("If-None-Match", ""), etag):
        return 304, b"", headers
    return status, body, headers
