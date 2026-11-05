"""Render the project's purpose, source conditions and publication limits."""

from pathlib import Path

from web_components import render_hero, render_notice, render_page
from web_components.static_text import read_static_text

INDEPENDENCE_NOTICE = (
    "<strong>Um projeto independente.</strong> Este site não é um órgão público. "
    "Citar uma instituição como fonte não significa parceria, apoio ou aprovação "
    "do projeto por essa instituição."
)


def render_project_information():
    content = read_static_text(Path(__file__).parent / "content.html")
    hero = render_hero(
        "Sobre o Se Liga, Brasil",
        "Dados públicos para entender a política",
        "Organizamos informações oficiais para ajudar qualquer pessoa a entender "
        "os cargos políticos, acompanhar decisões e conhecer o uso do dinheiro público.",
    )
    body = (
        f'<div class="ds-container institutional-notice">{render_notice(INDEPENDENCE_NOTICE)}</div>'
        f'<div class="ds-container institutional-prose">{content}</div>'
    )
    return render_page(
        "Sobre o projeto e os dados", hero + body,
        active_section="about", extra_stylesheet="/assets/civic-education.css",
    )
