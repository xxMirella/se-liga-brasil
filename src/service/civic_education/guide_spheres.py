"""Step 1 of the civic guide: who acts in each sphere (reference: Como Funciona v2)."""

from collections import namedtuple

from service.civic_education.guide_common import render_choice_check
from service.public_profile_web.security import text

SpherePanel = namedtuple(
    "SpherePanel",
    "label title scope executive executive_where executive_does"
    " legislative legislative_where legislative_does",
)

# Display order of the reference: Cidade, Estado, DF, País.
SPHERE_PANELS = {
    "municipal": SpherePanel(
        "Cidade", "Na sua cidade", "Decisões valem para o município",
        "Prefeito + vice", "Prefeitura e secretarias municipais",
        "Organiza serviços como postos de saúde, creches e ruas.",
        "Vereadores", "Câmara Municipal",
        "Propõem e votam leis da cidade e fiscalizam a prefeitura.",
    ),
    "estadual": SpherePanel(
        "Estado", "No seu estado", "Decisões valem para o estado",
        "Governador + vice", "Governo do estado e secretarias estaduais",
        "Organiza serviços como hospitais estaduais, escolas estaduais e polícia.",
        "Deputados estaduais", "Assembleia Legislativa",
        "Propõem e votam leis estaduais e fiscalizam o governo do estado.",
    ),
    "distrital": SpherePanel(
        "DF", "No Distrito Federal", "Reúne tarefas de estado e de município",
        "Governador + vice do DF", "Governo do Distrito Federal",
        "Cuida de atribuições estaduais e municipais. Não há prefeito de Brasília.",
        "Deputados distritais", "Câmara Legislativa",
        "Propõem e votam leis do DF e fiscalizam o governo. O DF não tem vereadores.",
    ),
    "federal": SpherePanel(
        "País", "No Brasil", "Decisões podem valer em todo o país",
        "Presidente + vice", "Governo federal e ministérios",
        "Chefia o governo federal. Não é chefe de governadores ou prefeitos.",
        "Deputados federais e senadores", "Congresso Nacional",
        "Propõem e votam leis federais e fiscalizam o governo federal.",
    ),
}
DEFAULT_PANEL = "municipal"
CONSTITUTION_SOURCE = (
    '<a href="https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm" '
    'target="_blank" rel="noopener noreferrer">'
    "Constituição Federal, arts. 2º, 18, 29 a 32, 44 a 52 e 84</a>"
)

STEP_LEAD = (
    "Cidade, estado e país têm cada um seu <strong>Executivo</strong>, que cuida dos serviços, "
    "e seu <strong>Legislativo</strong>, que vota regras e fiscaliza. Escolha um lugar."
)
SPHERE_QUESTION = (
    "O governador é chefe do prefeito?",
    (
        ("Sim", False, "Ainda não.",
         "Estado e município têm autonomia. Podem trabalhar juntos, mas isso não cria chefia."),
        ("Não", True, "Isso.",
         "Estado e município têm autonomia. Eles podem trabalhar juntos, mas isso não cria "
         "uma relação de chefia."),
    ),
)


def render_sphere_choices(selected):
    links = "".join(
        f'<a class="ds-civic-pill" href="?esfera={key}#passo-1"'
        + (' aria-current="true"' if key == selected else "")
        + f">{text(panel.label)}</a>"
        for key, panel in SPHERE_PANELS.items()
    )
    return f'<nav class="ds-civic-pills" aria-label="Escolha a esfera">{links}</nav>'


def render_power_card(kind, label, name, where, does):
    return f"""<div class="ds-civic-power ds-civic-power--{kind}">
<span class="ds-civic-power__label">{label}</span>
<strong class="ds-civic-power__name">{text(name)}</strong>
<span class="ds-civic-power__where">{text(where)}</span>
<span class="ds-civic-power__does">{text(does)}</span></div>"""


def render_sphere_panel(panel):
    executive = render_power_card(
        "executive", "Executivo · cuida dos serviços", panel.executive,
        panel.executive_where, panel.executive_does,
    )
    legislative = render_power_card(
        "legislative", "Legislativo · vota regras e fiscaliza", panel.legislative,
        panel.legislative_where, panel.legislative_does,
    )
    return f"""<div class="ds-civic-panel" id="mapa">
<div class="ds-civic-panel__head"><h3 class="ds-civic-panel__title">{text(panel.title)}</h3>
<span class="ds-civic-panel__scope">{text(panel.scope)}</span></div>
<div class="ds-civic-powers">{executive}{legislative}</div>
<div class="ds-civic-relation"><span aria-hidden="true">⇄</span>
<p><strong>Trabalham juntos em leis, orçamento e fiscalização.</strong> ⇄ significa relação
entre instituições. Não significa que uma manda na outra.</p></div></div>"""


EXTRA_DISCLOSURES = """<div class="ds-civic-disclosures">
<details class="ds-disclosure"><summary>E os vices e suplentes?</summary>
<div class="ds-disclosure__body"><p>Vices não ganham voto no Legislativo por serem vices.
Quando assumem o cargo do titular, exercem as competências daquele cargo. Suplentes só propõem
e votam como parlamentares quando assumem o mandato.</p></div></details>
<details class="ds-disclosure"><summary>Quem mais participa? Justiça, ministros e tribunais de
contas</summary>
<div class="ds-disclosure__body"><p>Juízes e tribunais julgam conflitos e verificam se as regras
respeitam a Constituição. Não são subordinados ao presidente. Municípios não têm um Poder
Judiciário próprio. Ministros e secretários ajudam a executar as políticas. Tribunais de contas
apoiam a fiscalização.</p></div></details></div>"""


def render_government_map(sphere="municipal"):
    panel = SPHERE_PANELS.get(sphere, SPHERE_PANELS[DEFAULT_PANEL])
    selected = sphere if sphere in SPHERE_PANELS else None
    question, options = SPHERE_QUESTION
    return f"""<section class="ds-civic-realms" aria-labelledby="map-title">
<span class="ds-civic-realms__eyebrow">Passo 1 de 4</span>
<h2 class="ds-civic-realms__title" id="map-title">Quem atua em cada lugar?</h2>
<p class="ds-civic-realms__lead">{STEP_LEAD}</p>
{render_sphere_choices(selected)}
{render_sphere_panel(panel)}
{EXTRA_DISCLOSURES}
{render_choice_check("esferas", question, options)}
<p class="ds-civic-realms__source">Fonte: {CONSTITUTION_SOURCE}
 · revisado em 18/10/2026</p></section>"""
