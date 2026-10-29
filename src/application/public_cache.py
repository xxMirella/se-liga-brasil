"""HTTP representations for public static content; dynamic data stays uncached."""

import gzip
import hashlib
from functools import lru_cache
from urllib.parse import urlsplit

STATIC_PAGE_PATHS = frozenset(
    {
        "/", "/como-funciona", "/sobre", "/sobre/", "/fontes-dos-dados", "/fontes-dos-dados/",
        "/comparacao-de-classificacoes", "/comparacao-de-classificacoes/",
    }
)


def public_cache_policy(target, status):
    if status != 200:
        return "no-store"
    path = urlsplit(target).path
    if path in {"/panorama", "/api/political-dashboard"}:
        return "public, max-age=60, s-maxage=300, stale-while-revalidate=300"
    if path in STATIC_PAGE_PATHS:
        return "public, max-age=60, s-maxage=3600, stale-while-revalidate=86400"
    if path in {
        "/assets/public-profile.css",
        "/assets/civic-education.css",
        "/assets/brazil-flag.svg",
        "/favicon.ico",
        "/assets/panorama.css",
        "/assets/party-comparison.css",
        "/assets/people-viewport.js",
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


def public_representation(body, accept_encoding, dataset_version=None):
    compressed = len(body) >= 1024 and accepts_gzip(accept_encoding)
    representation = compressed_body(body) if compressed else body
    digest = hashlib.sha256()
    if dataset_version:
        # A new published dataset changes the validator even if a body happened to be equal.
        digest.update(dataset_version.encode() + b"\0")
    digest.update(representation)
    etag = '"' + digest.hexdigest() + '"'
    return representation, etag, compressed


def matches_etag(header, etag):
    return any(value.strip().removeprefix("W/") in {etag, "*"} for value in header.split(","))


def prepare_public_response(target, status, body, request_headers, dataset_version=None):
    policy = public_cache_policy(target, status)
    headers = {"Cache-Control": policy}
    if policy == "no-store":
        return status, body, headers
    body, etag, compressed = public_representation(
        body, request_headers.get("Accept-Encoding", ""), dataset_version
    )
    headers.update({"ETag": etag, "Vary": "Accept-Encoding"})
    if compressed:
        headers["Content-Encoding"] = "gzip"
    if matches_etag(request_headers.get("If-None-Match", ""), etag):
        return 304, b"", headers
    return status, body, headers
