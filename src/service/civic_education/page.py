"""An accessible, paced civic guide; complete as HTML, with scripts only as enhancement."""

from pathlib import Path

from service.civic_education.guide_common import SPHERES, source_link  # noqa: F401
from service.civic_education.guide_laws import render_law_flow, render_law_types
from service.civic_education.guide_offices import render_offices
from service.civic_education.guide_review import render_practice
from service.civic_education.guide_spheres import render_government_map
from service.public_profile.contracts import PublicProfileError
from web_components import SCROLL_REVEAL_SCRIPT, render_hero, render_page
from web_components.static_text import read_static_text

STYLESHEET_PARTS = (
    "civic-education.css", "guide-spheres.css", "guide-offices.css", "guide-laws.css",
    "guide-review.css",
)


def civic_stylesheet():
    directory = Path(__file__).parent / "assets"
    return "\n".join(read_static_text(directory / name) for name in STYLESHEET_PARTS)


ENHANCEMENT_SCRIPTS = (
    SCROLL_REVEAL_SCRIPT, "/assets/civic-guide.js", "/assets/civic-review.js",
)

STEPS = (
    ("Esferas", "Passo 1 Esferas"),
    ("Cargos", "Passo 2 Cargos"),
    ("Leis", "Passo 3 Leis"),
    ("Revisão", "Passo 4 Revisão"),
)

PRINCIPLE_NOTICE = """<div class="ds-civic-principle"><strong>Não é uma escada de chefes.</strong>
<p>O presidente chefia o governo federal. Não é chefe dos governadores ou dos prefeitos.
O governo cuida dos serviços. O Legislativo vota regras e fiscaliza. A Justiça julga conflitos.
Cada um tem limites.</p></div>"""


def render_step_navigation():
    items = "".join(
        f'<li><a class="ds-civic-stepper__link" href="#passo-{number}">'
        '<span class="ds-civic-stepper__bar"></span>'
        f'<span class="ds-civic-stepper__label"><span>{number}</span> {label}</span></a></li>'
        for number, (label, _) in enumerate(STEPS, 1)
    )
    return f'<nav class="ds-civic-stepper" aria-label="Passos do guia"><ol>{items}</ol></nav>'


def render_step(number, content_html):
    """Anchor wrapper of a step; the step owns its own heading, so this adds none."""
    label = STEPS[number - 1][1]
    return (
        f'<div class="ds-civic-step-anchor" id="passo-{number}" data-screen-label="{label}">'
        f"{content_html}</div>"
    )


def render_guide_introduction():
    hero = render_hero(
        "Guia para quem está começando",
        "Quem faz o quê na política?",
        "Entenda os cargos e o caminho das leis, uma parte de cada vez. "
        "Leva cerca de 10 minutos.",
    )
    return (
        hero
        + f'<div class="ds-container ds-civic-principle-row">{PRINCIPLE_NOTICE}</div>'
        + render_step_navigation()
        + '<div class="ds-container civic-guide">'
    )


def render_civic_education(sphere="municipal"):
    if sphere not in {*SPHERES, "todos"}:
        raise PublicProfileError("INVALID_EDUCATION_SPHERE")
    content = render_guide_introduction()
    content += render_step(1, render_government_map(sphere))
    content += render_step(2, render_offices(sphere))
    content += render_step(3, render_law_flow(sphere) + render_law_types())
    content += render_step(4, render_practice()) + "</div>"
    return render_page(
        "Quem faz o quê na política?",
        content,
        extra_stylesheet="/assets/civic-education.css",
        active_section="guide",
        footer_notes_html=render_research_note(),
        scripts=ENHANCEMENT_SCRIPTS,
    )


def render_research_note():
    return """<details class="ds-disclosure ds-civic-research">
<summary>Fontes e como este guia foi desenhado</summary><div class="ds-disclosure__body">
<p>Conteúdo jurídico revisado em 18/10/2026. É uma introdução: regras estaduais, leis orgânicas e
regimentos podem acrescentar etapas.</p>
<p>O desenho usa partes curtas, rótulos junto das relações e perguntas com respostas para
consultar. A compreensão deste guia por crianças de 10 anos ainda não foi testada.</p>
</div></details>"""
