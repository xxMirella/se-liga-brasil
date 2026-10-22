"""Render the project's purpose, source conditions and publication limits."""

from pathlib import Path

from service.public_profile_web.layout import render_layout


def render_project_information():
    content = (Path(__file__).parent / "content.html").read_text(encoding="utf-8")
    return render_layout(
        "Sobre o projeto e os dados", content,
        extra_stylesheet="/assets/civic-education.css", active_section="about",
    )
