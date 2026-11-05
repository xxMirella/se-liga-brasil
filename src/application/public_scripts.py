"""Serve the front-end scripts of the public portal as same-origin assets (script-src 'self')."""

from pathlib import Path

import service.civic_education as civic_education
import service.public_profile_web as public_profile_web
import web_components
from application.public_portal import encode_response
from web_components.static_text import read_static_text

SCRIPT_FILES = {
    "/assets/people-search-enhance.js": Path(public_profile_web.__file__).parent / "assets"
    / "people-search-enhance.js",
    "/assets/profile-activity.js": Path(web_components.__file__).parent / "assets"
    / "profile-activity.js",
    "/assets/civic-guide.js": Path(civic_education.__file__).parent / "assets"
    / "civic-guide.js",
    "/assets/scroll-reveal.js": Path(web_components.__file__).parent / "assets"
    / "scroll-reveal.js",
    "/assets/panorama-enhance.js": Path(web_components.__file__).parent / "assets"
    / "panorama-enhance.js",
    "/assets/civic-review.js": Path(civic_education.__file__).parent / "assets"
    / "civic-review.js",
}


def route_script_request(parsed):
    """Return the script response for a known script path without a query, else None."""
    script = None if parsed.query else SCRIPT_FILES.get(parsed.path)
    if script is None:
        return None
    return encode_response(read_static_text(script), content_type="text/javascript")
