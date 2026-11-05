"""Step 3 of the civic guide: how an idea becomes law, and law types (texts as in the reference)."""

from service.civic_education.laws import (
    LAW_NORMS,
    LAW_PUBLICATION_STEP,
    LAW_ROUTES,
    LAW_SOURCE_LINKS,
    LAW_VETO_ANSWER,
)
from service.public_profile_web.security import text

# Order and labels of the sphere pills (sphere key, label), as in the reference.
LAW_SPHERE_CHOICES = (
    ("municipal", "Cidade"),
    ("estadual", "Estado"),
    ("distrital", "DF"),
    ("federal", "País"),
)

EXTERNAL = 'target="_blank" rel="noopener noreferrer"'

TERM_DEFINITIONS = (
    (
        "Sanção",
        "termo-sancao",
        "o presidente, governador ou prefeito concorda com um projeto de lei aprovado. "
        "Em algumas situações, o silêncio no prazo legal também vale como sanção.",
    ),
    (
        "Veto",
        "termo-veto",
        "o presidente, governador ou prefeito rejeita todo ou parte de um projeto, com "
        "justificativa. O Legislativo pode reexaminar essa rejeição.",
    ),
)

PEC_CHECK = (
    "Uma PEC aprovada precisa da assinatura do presidente?",
    (
        (
            "sim", "Sim", False,
            "As Mesas da Câmara e do Senado promulgam a emenda. Não há sanção nem veto "
            "presidencial.",
        ),
        (
            "nao", "Não", True,
            "Depois das aprovações nas duas Casas, as Mesas da Câmara e do Senado promulgam "
            "a emenda.",
        ),
    ),
)


def _render_term_panel(term, anchor, definition):
    return (
        f'<div class="ds-civic-law__term-panel" id="{anchor}">'
        f"<strong>{text(term)}:</strong> {text(definition)}</div>"
    )


def _render_intro():
    panels = "".join(_render_term_panel(*term) for term in TERM_DEFINITIONS)
    return (
        '<p class="ds-civic-law__intro">Ninguém aprova uma lei sozinho. Em geral, alguém propõe, '
        "o Legislativo vota e o Executivo pode "
        '<a class="ds-civic-law__term" href="#termo-sancao">sancionar</a> ou '
        '<a class="ds-civic-law__term" href="#termo-veto">vetar</a>.</p>' + panels
    )


def _render_sphere_choice(key, label, current):
    marker = ' aria-current="true"' if key == current else ""
    return f'<a class="ds-civic-law__sphere" href="?esfera={key}#leis"{marker}>{label}</a>'


def _render_sphere_choices(sphere):
    current = "federal" if sphere == "todos" else sphere
    links = "".join(_render_sphere_choice(key, label, current) for key, label in LAW_SPHERE_CHOICES)
    return f'<nav class="ds-civic-law__spheres" aria-label="Escolha a esfera">{links}</nav>'


def _render_flow_steps(proposal, vote, answer):
    steps = (
        ("Uma proposta", proposal),
        ("Análise e votação", vote),
        ("O Executivo responde", answer),
        ("A lei é publicada", LAW_PUBLICATION_STEP),
    )
    items = "".join(
        f'<li><span class="ds-civic-law__number">{index}</span><div><strong>{name}</strong>'
        f"<span>{text(body)}</span></div></li>"
        for index, (name, body) in enumerate(steps, 1)
    )
    return f'<ol class="ds-civic-law__steps">{items}</ol>'


def _render_flow_card(sphere):
    law_of, proposal, vote, answer = LAW_ROUTES[sphere if sphere != "todos" else "federal"]
    return (
        '<div class="ds-civic-law__card">'
        f'<h3 class="ds-civic-law__card-title">Lei {text(law_of)} · caminho geral</h3>'
        + _render_sphere_choices(sphere)
        + _render_flow_steps(proposal, vote, answer)
        + '<details class="ds-disclosure ds-civic-law__more"><summary>E se houver veto?'
        f"</summary><p>{text(LAW_VETO_ANSWER)}</p></details></div>"
    )


def _render_sources():
    links = " · ".join(
        f'<a href="{text(url)}" {EXTERNAL}>{text(label)}</a>' for label, url in LAW_SOURCE_LINKS
    )
    return f'<p class="ds-civic-law__sources">Fontes: {links} · revisado em 18/10/2026</p>'


def render_law_flow(sphere):
    """Render the whole Step 3 section: flow card, norm list, self-check and sources."""
    return f"""<section class="ds-section ds-civic-law" id="leis">
<span class="ds-civic-law__eyebrow">Passo 3 de 4</span>
<h2 class="ds-heading ds-civic-law__title">Como uma ideia vira lei?</h2>
{_render_intro()}
<div class="ds-civic-law__layout">{_render_flow_card(sphere)}{_render_law_column()}</div>
{_render_check(*PEC_CHECK)}
{_render_sources()}</section>"""


def _render_norm(row):
    title, tag, proposer, voter, finalizer, example, url = row
    kind = "with" if tag == "Tem sanção" else "without"
    return f"""<details class="ds-disclosure ds-civic-law__norm"><summary><span>{text(title)}</span>
<span class="ds-civic-law__tag ds-civic-law__tag--{kind}">{text(tag)}</span></summary>
<dl><div><dt>Quem propõe</dt><dd>{text(proposer)}</dd></div>
<div><dt>Quem aprova</dt><dd>{text(voter)}</dd></div>
<div><dt>Como termina</dt><dd>{text(finalizer)}</dd></div>
<div><dt>Exemplo</dt><dd>
<a href="{text(url)}" {EXTERNAL}>{text(example)}</a></dd></div></dl></details>"""


def render_law_types():
    """The norm list lives beside the flow card (reference layout); page.py still calls this."""
    return ""


def _render_law_column():
    rows = "".join(_render_norm(row) for row in LAW_NORMS)
    return f"""<div class="ds-civic-law__column" id="tipos">
<h3 class="ds-civic-law__column-title">Nem toda regra segue esse caminho</h3>
<p>Cada tipo de norma tem quem propõe, quem aprova e como termina.
Escolha um para ver o resumo.</p>
<div class="ds-civic-law__norms">{rows}</div>
<p class="ds-civic-law__legend">Etiqueta: se a norma passa por sanção ou veto do Executivo.
</p></div>"""


def _render_check_option(key, label, picked_anchor):
    return f'<a class="ds-civic-law__option" href="#{picked_anchor}-{key}">{text(label)}</a>'


def _render_check_feedback(anchor, key, correct, feedback):
    verdict = "Isso." if correct else "Ainda não."
    kind = "right" if correct else "wrong"
    return (
        f'<div class="ds-civic-law__feedback ds-civic-law__feedback--{kind}" '
        f'id="{anchor}-{key}" role="status"><strong>{verdict}</strong> {text(feedback)}</div>'
    )


def _render_check(question, options):
    anchor = "checagem-pec"
    buttons = "".join(_render_check_option(key, label, anchor) for key, label, *_ in options)
    feedback = "".join(
        _render_check_feedback(anchor, key, correct, note) for key, _, correct, note in options
    )
    return f"""<div class="ds-civic-law__check">
<span class="ds-civic-law__check-label">Checagem · pense antes de escolher</span>
<p class="ds-civic-law__question">{text(question)}</p>
<div class="ds-civic-law__options">{buttons}</div>{feedback}</div>"""
