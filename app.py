"""Vercel's production WSGI entrypoint; never starts the local HTTP server."""

from application.vercel import PublicPortalWSGI

app = PublicPortalWSGI()
