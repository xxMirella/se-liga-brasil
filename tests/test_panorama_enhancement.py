from urllib.parse import urlsplit

from application.public_cache import public_cache_policy
from application.public_scripts import SCRIPT_FILES, route_script_request
from web_components import render_page


def test_render_page_loads_each_script_deferred_from_the_same_origin():
    html = render_page("T", "<p>x</p>", active_section="panorama", scripts=("/assets/a.js",))

    assert '<script src="/assets/a.js" defer></script>' in html
    assert "<script>" not in html


def test_render_page_without_scripts_has_no_script_tag():
    assert "<script" not in render_page("T", "<p>x</p>", active_section="panorama")


def test_panorama_enhancement_script_is_served_as_javascript():
    response = route_script_request(urlsplit("/assets/panorama-enhance.js"))

    assert response.status == 200
    assert response.content_type.startswith("text/javascript")
    assert b"/panorama" in response.body


def test_script_route_ignores_queries_and_unknown_paths():
    assert route_script_request(urlsplit("/assets/panorama-enhance.js?x=1")) is None
    assert route_script_request(urlsplit("/assets/other.js")) is None


def test_every_served_script_is_revalidated_by_the_cache():
    for path in SCRIPT_FILES:
        assert "must-revalidate" in public_cache_policy(path, 200)


def test_scroll_reveal_script_is_shared_by_the_panorama_and_the_profile_pages():
    from application.public_portal import dispatch_portal_request
    from service.public_profile_web.pages import render_person_profile  # noqa: F401

    response = dispatch_portal_request(object(), "/assets/scroll-reveal.js")
    script = response.body.decode()

    assert response.status == 200
    assert "ds:content-replaced" in script
    assert ".ds-profile-summary__card" in script and ".ds-period-card" in script
    for forbidden in ("innerHTML", "eval(", "document.write"):
        assert forbidden not in script


def test_civic_review_script_is_served_and_safe():
    response = route_script_request(urlsplit("/assets/civic-review.js"))
    script = response.body.decode()

    assert response.status == 200 and response.content_type.startswith("text/javascript")
    assert "data-civic-review" in script and "aria-pressed" in script
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "document.write"):
        assert forbidden not in script
    assert "must-revalidate" in public_cache_policy("/assets/civic-review.js", 200)
