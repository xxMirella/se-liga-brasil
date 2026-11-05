"""Vercel Web Analytics for the public portal, without a Node package.

Vercel serves the tracking script itself at /_vercel/insights/script.js once Web Analytics is
enabled for the project, so a plain script tag is all a Python site needs. The tag is added only
to production HTML: previews, local runs and the static export stay free of it. The script and the
page-view beacon are same-origin, so the existing content security policy already allows them.
"""

import os
from dataclasses import replace

ANALYTICS_SCRIPT_TAG = b'<script defer src="/_vercel/insights/script.js"></script>'
HEAD_CLOSING_TAG = b"</head>"
PRODUCTION_ENVIRONMENT = "production"


def is_web_analytics_enabled(environ=None):
    environment = os.environ if environ is None else environ
    return environment.get("VERCEL_ENV") == PRODUCTION_ENVIRONMENT


def add_web_analytics(response, environ=None):
    """Return the response with the analytics tag in <head>; other responses are untouched."""
    is_page = response.status == 200 and response.content_type.startswith("text/html")
    if not is_page or not is_web_analytics_enabled(environ):
        return response
    if ANALYTICS_SCRIPT_TAG in response.body or HEAD_CLOSING_TAG not in response.body:
        return response
    body = response.body.replace(HEAD_CLOSING_TAG, ANALYTICS_SCRIPT_TAG + HEAD_CLOSING_TAG, 1)
    return replace(response, body=body)
