"""Contract of web_components: escaping, accessibility, no inline styles, self-hosted fonts."""

from web_components import (
    design_system_stylesheet,
    render_card,
    render_page,
    render_site_header,
    render_tab_links,
)


def test_header_marks_only_active_section_and_escapes_query():
    header = render_site_header("panorama", query='"><script>')
    assert header.count('aria-current="page"') == 1
    assert 'href="/panorama" aria-current="page"' in header
    assert "<script>" not in header


def test_page_has_skip_link_main_and_footer_without_inline_style_or_script():
    document = render_page("Teste", "<p>x</p>", active_section="about")
    assert 'href="#main"' in document and '<main id="main">' in document
    assert "<footer" in document
    assert " style=" not in document and "<script" not in document


def test_components_escape_text_arguments():
    assert "&lt;b&gt;" in render_card("<b>", text="<i>")
    assert "&lt;i&gt;" in render_card("x", text="<i>")
    tabs = render_tab_links("Casa", [("Senado", "/panorama?house=senado", True)])
    assert 'aria-current="page"' in tabs


def test_stylesheet_has_tokens_and_components():
    stylesheet = design_system_stylesheet()
    assert "--color-brand" in stylesheet and ".ds-site-header" in stylesheet


def test_font_faces_point_to_existing_self_hosted_files():
    import re

    from web_components import font_file_names

    stylesheet = design_system_stylesheet()
    urls = re.findall(r'url\("/assets/fonts/([^"]+)"\)', stylesheet)
    assert urls and set(urls) <= set(font_file_names())
    assert "fonts.googleapis.com" not in stylesheet


def test_font_reader_only_serves_allow_listed_files():
    from web_components import read_font_file

    assert read_font_file("/assets/fonts/public-sans-latin-400-normal.woff2")[:4] == b"wOF2"
    assert read_font_file("/assets/fonts/../fonts.py") is None
    assert read_font_file("/assets/fonts/%2e%2e/x.woff2") is None
    assert read_font_file("/assets/other.woff2") is None


def test_portal_serves_fonts_with_immutable_cache_and_csp_allows_them():
    from application.public_cache import public_cache_policy
    from application.public_portal import dispatch_portal_request
    from application.vercel import CONTENT_SECURITY_POLICY

    response = dispatch_portal_request(object(), "/assets/fonts/newsreader-latin-400-normal.woff2")
    assert response.status == 200 and response.content_type == "font/woff2"
    assert "immutable" in public_cache_policy("/assets/fonts/x.woff2", 200)
    assert "font-src 'self'" in CONTENT_SECURITY_POLICY
    assert dispatch_portal_request(object(), "/assets/fonts/nao-existe.woff2").status == 404


def test_static_build_fingerprints_fonts_and_rewrites_stylesheets(tmp_path):
    from service.static_publication.build import build_civic_site

    build_civic_site(tmp_path)
    fonts = list((tmp_path / "assets" / "fonts").glob("*.woff2"))
    assert len(fonts) == 8
    stylesheet = next(tmp_path.glob("assets/public-profile.*.css")).read_text()
    assert "/assets/fonts/newsreader-latin-400-normal.woff2" not in stylesheet
    assert all(font.name in stylesheet for font in fonts if "newsreader-latin-400" in font.name)
    assert "font-src 'self'" in (tmp_path / "_headers").read_text()


def test_footer_sticks_to_bottom_of_short_pages():
    stylesheet = design_system_stylesheet()
    assert "min-height: 100dvh" in stylesheet
    assert "main { flex: 1 0 auto; }" in stylesheet


def test_stacked_bar_uses_col_widths_and_bloc_classes_without_inline_style():
    from web_components import BarSegment, render_stacked_bar

    html = render_stacked_bar(
        [BarSegment("left", 40, "40%"), BarSegment("far_right", 5, "5%"), BarSegment("center", 0)],
        "Câmara", half_marker=True,
    )
    assert '<col width="40.00%">' in html and "ds-bloc--far-right" in html
    assert "ds-stacked-bar--half" in html and " style=" not in html
    assert ">40%<" in html and ">5%<" not in html  # narrow segments carry no label
