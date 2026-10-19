"""Deterministic static documents, fingerprinted assets and compressed representations."""

import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from service.civic_education.page import SPHERES, civic_stylesheet, render_civic_education
from service.public_profile_web.layout import public_stylesheet

SPHERE_NAMES = (*SPHERES, "todos")


def validate_backend_origin(origin):
    if origin is None:
        return ""
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in origin)
        or any(character in origin for character in "<>\"\\'")
    ):
        raise ValueError("Backend origin must be an HTTPS origin without credentials or path")
    return origin.rstrip("/")


def write_representation(directory, relative, body):
    path = directory / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.with_name(path.name + ".gz").write_bytes(gzip.compress(body, mtime=0))
    return {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}


def render_static_page(sphere, asset_paths, backend_origin):
    document = render_civic_education(sphere)
    for original, fingerprinted in asset_paths.items():
        document = document.replace(original, fingerprinted)
    for selected in SPHERE_NAMES:
        document = document.replace(
            f'"?esfera={selected}#cargos"', f'"/como-funciona/{selected}/#cargos"'
        )
    document = document.replace('"/como-funciona"', '"/como-funciona/"')
    if backend_origin:
        document = document.replace('"/pessoas"', f'"{backend_origin}/pessoas"')
    return document.encode("utf-8")


def hosting_headers(backend_origin):
    policy = (
        "default-src 'none'; style-src 'self'; img-src 'self' https:; "
        f"form-action 'self' {backend_origin}; base-uri 'none'; frame-ancestors 'none'"
    )
    return f"""/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Content-Security-Policy: {policy}
  Cache-Control: public, max-age=0, must-revalidate
/assets/*
  Cache-Control: public, max-age=31536000, immutable
/como-funciona/*
  Cache-Control: public, max-age=60, s-maxage=3600, stale-while-revalidate=86400
"""


def build_civic_site(output_directory, *, backend_origin=None):
    origin = validate_backend_origin(backend_origin)
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    asset_paths, files = {}, {}
    for name, stylesheet in (
        ("public-profile", public_stylesheet()),
        ("civic-education", civic_stylesheet()),
    ):
        body = stylesheet.encode("utf-8")
        fingerprint = hashlib.sha256(body).hexdigest()[:16]
        relative = f"assets/{name}.{fingerprint}.css"
        asset_paths[f"/assets/{name}.css"] = "/" + relative
        files[relative] = write_representation(directory, relative, body)
    for sphere in SPHERE_NAMES:
        relative = f"como-funciona/{sphere}/index.html"
        files[relative] = write_representation(
            directory, relative, render_static_page(sphere, asset_paths, origin)
        )
    for relative in ("index.html", "como-funciona/index.html"):
        files[relative] = write_representation(
            directory, relative, render_static_page("municipal", asset_paths, origin)
        )
    (directory / "_headers").write_text(hosting_headers(origin), encoding="utf-8")
    manifest = {"version": 1, "backend_origin": origin or None, "files": files}
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"output_directory": str(directory.resolve()), "files": len(files)}
