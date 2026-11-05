from application.public_portal import PublicResponse
from application.web_analytics import (
    ANALYTICS_SCRIPT_TAG,
    add_web_analytics,
    is_web_analytics_enabled,
)

PRODUCTION = {"VERCEL_ENV": "production"}
PAGE = b"<!doctype html><html><head><title>x</title></head><body>conteudo</body></html>"


def html_response(body=PAGE, status=200, content_type="text/html; charset=utf-8"):
    return PublicResponse(status, body, content_type)


def test_production_html_gets_the_tag_once_inside_head():
    response = add_web_analytics(html_response(), PRODUCTION)

    assert response.body.count(ANALYTICS_SCRIPT_TAG) == 1
    assert response.body.index(ANALYTICS_SCRIPT_TAG) < response.body.index(b"</head>")
    assert add_web_analytics(response, PRODUCTION).body == response.body


def test_only_production_is_tracked():
    for environ in ({}, {"VERCEL_ENV": "preview"}, {"VERCEL_ENV": "development"}):
        assert add_web_analytics(html_response(), environ).body == PAGE
        assert not is_web_analytics_enabled(environ)


def test_errors_json_and_assets_are_never_changed():
    cases = [
        html_response(status=404),
        html_response(status=503),
        html_response(b'{"a": 1}', content_type="application/json"),
        html_response(b"body{}", content_type="text/css"),
        html_response(b"<p>sem head</p>"),
    ]
    for response in cases:
        assert add_web_analytics(response, PRODUCTION) == response


def test_the_script_is_a_same_origin_file_so_the_policy_needs_no_new_source():
    from application.vercel import CONTENT_SECURITY_POLICY

    assert b'src="/_vercel/insights/script.js"' in ANALYTICS_SCRIPT_TAG
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY
    assert "connect-src 'self'" in CONTENT_SECURITY_POLICY
