"""Render the project's purpose, source conditions and publication limits."""

from pathlib import Path

from service.public_profile_web.layout import render_layout
from service.public_profile_web.static_text import read_static_text


def render_project_information():
    content = read_static_text(Path(__file__).parent / "content.html")
    return render_layout(
        "Sobre o projeto e os dados", content,
        extra_stylesheet="/assets/civic-education.css", active_section="about",
    )
