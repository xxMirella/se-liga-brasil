"""Page layout adapter: wraps content with the shared web_components shell and stylesheet."""

from pathlib import Path

from service.public_profile_web.static_text import read_static_text
from web_components import design_system_stylesheet, render_page


def public_stylesheet():
    page_styles = read_static_text(Path(__file__).parent / "assets" / "public-profile.css")
    return design_system_stylesheet() + "\n" + page_styles


def public_favicon():
    return read_static_text(Path(__file__).parent / "assets" / "brazil-flag.svg")


def render_layout(title, content, query="", *, extra_stylesheet=None, active_section="people",
                  scripts=(), workspace_class="workspace", footer_notes_html=""):
    return render_page(
        title, f'<div class="{workspace_class}">{content}</div>',
        active_section=active_section, query=query, extra_stylesheet=extra_stylesheet,
        scripts=scripts, footer_notes_html=footer_notes_html,
    )
