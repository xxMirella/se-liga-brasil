"""Step 2 of the civic guide: what each office can do (reference: Como Funciona v2)."""

from service.civic_education.guide_common import SPHERES, render_choice_check, source_link
from service.civic_education.office_cards import OFFICE_CARDS
from service.public_profile_web.security import text

# The reference lists the Federal District before the country.
SELECTOR_ORDER = ("municipal", "estadual", "distrital", "federal")
SPHERE_IN_SENTENCE = {
    "municipal": "cidade",
    "estadual": "estado",
    "distrital": "Distrito Federal",
    "federal": "país",
    "todos": "todas as esferas",
}
POWER_TONES = {"Executivo": "executive", "Legislativo": "legislative"}

INTRODUCTION = """<details class="ds-disclosure ds-civic-intro">
<summary>Antes de começar: UBS, UPA e hospital, e quem administra cada um</summary>
<div class="ds-disclosure__body">
<p>A UBS é o posto de saúde, usado para consultas e acompanhamento. A UPA atende urgências.
Hospitais têm serviços como internações e cirurgias. Eles trabalham em rede.</p>
<p>Nem toda UPA ou hospital é da prefeitura. A gestão pode ser municipal, estadual, distrital
ou federal. Receber dinheiro de outro governo não muda automaticamente quem administra
o local.</p></div></details>"""


def render_rule(label, content):
    return f'<div class="ds-civic-office__rule"><dt>{label}</dt><dd>{text(content)}</dd></div>'


def render_office_card(card):
    power, name, where, summary, can, cannot, depends, health, source, url = card
    tone = POWER_TONES[power]
    rules = (
        render_rule("Pode", can) + render_rule("Não pode", cannot)
        + render_rule("Depende de", depends)
    )
    return f"""<article class="ds-civic-office">
<span class="ds-civic-office__label ds-civic-office__label--{tone}">{power} · {text(where)}</span>
<h3 class="ds-civic-office__name">{text(name)}</h3>
<p class="ds-civic-office__summary">{text(summary)}</p>
<dl class="ds-civic-office__rules">{rules}</dl>
<details class="ds-disclosure ds-civic-rules"><summary>Exemplo na saúde</summary>
<div class="ds-disclosure__body"><p>{text(health)}</p></div></details>
<span class="ds-civic-office__source">Fonte: {source_link((source, url))}</span>
</article>"""


def render_sphere_selector(selected):
    links = "".join(
        f'<a class="ds-civic-sphere" href="?esfera={key}#cargos"'
        + (' aria-current="true"' if key == selected else "")
        + f">{text(SPHERES[key])}</a>"
        for key in SELECTOR_ORDER
    )
    return f"""<div class="ds-civic-toolbar">
<nav class="ds-civic-spheres" aria-label="Escolha a esfera">{links}</nav>
<p class="ds-civic-toolbar__note">Exemplos de competências, não obras ou resultados
de uma pessoa.</p>
</div>"""


def render_office_check():
    return render_choice_check(
        "cargos",
        "A UBS municipal está com goteira. Quem organiza o conserto?",
        (
            (
                "Vereador", False, "Ainda não.",
                "O vereador pode cobrar a prefeitura e fiscalizar os gastos, "
                "mas não executa o conserto.",
            ),
            (
                "Prefeitura", True, "Isso.",
                "Se a UBS é municipal, a prefeitura organiza o reparo, "
                "seguindo as regras e o orçamento.",
            ),
            ("Governador", False, "Ainda não.", "O governador não comanda a rede municipal."),
        ),
    )


def render_offices(sphere):
    spheres = SELECTOR_ORDER if sphere == "todos" else (sphere,)
    cards = "".join(render_office_card(card) for key in spheres for card in OFFICE_CARDS[key])
    return f"""<section class="ds-section ds-civic-step" id="cargos">
<span class="ds-eyebrow ds-civic-step__eyebrow">Passo 2 de 4</span>
<h2 class="ds-civic-step__title">O que cada cargo pode fazer?</h2>
<p class="ds-civic-step__lead">Vamos usar a saúde como exemplo: quem pode resolver um problema no
posto de saúde? Os cargos abaixo são de <strong>{SPHERE_IN_SENTENCE[sphere]}</strong>.</p>
{render_sphere_selector(sphere)}
{INTRODUCTION}
<div class="ds-civic-offices">{cards}</div>
{render_office_check()}
</section>"""
