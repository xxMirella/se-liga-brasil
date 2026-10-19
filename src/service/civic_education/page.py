"""An accessible, paced civic guide rendered as HTML without executable client code."""

from pathlib import Path

from service.civic_education.diagrams import render_circle_section
from service.civic_education.health_offices import render_health_context, render_health_examples
from service.civic_education.law_examples import render_law_description
from service.civic_education.laws import GLOSSARY, LAW_ROUTES, LAW_SOURCES, LAW_TYPES
from service.civic_education.office_decisions import OFFICE_DECISIONS
from service.civic_education.office_locations import render_office_location
from service.civic_education.offices import OFFICES, SOURCES
from service.civic_education.simple_offices import SIMPLE_OFFICES
from service.public_profile.contracts import PublicProfileError
from service.public_profile_web.layout import render_layout
from service.public_profile_web.security import text

SPHERES = {"municipal": "Cidade", "estadual": "Estado", "federal": "País", "distrital": "DF"}
MAP_ROWS = (
    ("municipal", "Sua cidade", "Prefeito + vice", "Vereadores", "Câmara Municipal"),
    (
        "estadual",
        "Seu estado",
        "Governador + vice",
        "Deputados estaduais",
        "Assembleia Legislativa",
    ),
    (
        "federal",
        "O país",
        "Presidente + vice",
        "Deputados federais + senadores",
        "Congresso Nacional",
    ),
)


def civic_stylesheet():
    return (Path(__file__).parent / "assets" / "civic-education.css").read_text(encoding="utf-8")


def source_link(source, reference=""):
    title, url = source
    suffix = " · " + reference if reference else ""
    return (
        f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">'
        f"{text(title + suffix)}</a>"
    )


def render_map_row(row):
    sphere, label, executive, legislative, house = row
    return f"""<div class="civic-map-row"><div class="civic-sphere">{text(label)}</div>
<div class="civic-node">
<small>EXECUTIVO · CUIDA DOS SERVIÇOS</small>
<strong>{text(executive)}</strong>
</div>
<div class="civic-relationship">
<span aria-hidden="true">⇄</span>
<span>Leis, orçamento<br>e fiscalização</span>
</div>
<div class="civic-node">
<small>LEGISLATIVO · VOTA REGRAS E FISCALIZA</small>
<strong>{text(legislative)}</strong>
<span>{text(house)}</span>
</div>
<a class="civic-explore" href="?esfera={sphere}#cargos">Explorar</a>
</div>
"""


def render_government_map():
    rows = "".join(render_map_row(row) for row in MAP_ROWS)
    return f"""<section id="mapa" aria-labelledby="map-title">
<h2 id="map-title">Quem cuida de quê?</h2>
<p>Abrangência: cidade, estado e país. Cada esfera tem suas próprias responsabilidades.</p>
<div class="civic-map" role="group" aria-label="Esferas autônomas e relação entre os
Poderes">{rows}</div>
<p class="civic-key">⇄ significa relação entre instituições. <strong>Não significa que uma manda
na outra.</strong>
</p>
<aside class="civic-note"><strong>E o Distrito Federal?</strong> Não tem municípios.
Seu governador e a Câmara Legislativa cuidam de atribuições estaduais e municipais.
<a href="?esfera=distrital#cargos">Entender o DF</a>.</aside>
<details><summary>Quem mais participa?</summary><p>Juízes e tribunais julgam conflitos e verificam
se as regras respeitam a Constituição. Não são subordinados ao presidente. Municípios não têm
um Poder Judiciário próprio.</p><p>Ministros e secretários ajudam a executar as políticas.
Há chefia administrativa dentro de cada Executivo. Tribunais de contas apoiam a fiscalização;
Ministério Público e tribunais não são uma etapa obrigatória da aprovação de toda lei.</p>
{source_link(SOURCES["constitution"], "arts. 2º, 18, 31, 84, 87 e 92")}</details></section>"""


def render_office_card(office):
    key, sphere, title, does, cannot, dependencies, source, reference = office
    simple = SIMPLE_OFFICES[key]
    proposal, vote, reach = OFFICE_DECISIONS[key]
    return f"""<article class="civic-office" id="cargo-{key}">
<p class="category">{SPHERES[sphere]}</p>
<h3>{text(title)}</h3>{render_office_location(key)}
{render_health_examples(key)}<dl><dt>O que faz</dt><dd>{text(simple[0])}</dd>
<dt>O que não faz</dt><dd>{text(simple[1])}</dd>
<dt>De quem precisa</dt><dd>{text(simple[2])}</dd>
<dt>Pode apresentar propostas?</dt><dd>{text(proposal)}</dd>
<dt>Vota e aprova leis?</dt><dd>{text(vote)}</dd>
<dt>Quem é atendido ou afetado?</dt><dd>{text(reach)}</dd></dl>
<details><summary>Ver detalhes e fonte oficial</summary>
<p><strong>Atuação:</strong> {text(does)}</p><p><strong>Limite:</strong> {text(cannot)}</p>
<p><strong>Relação:</strong> {text(dependencies)}</p>
{source_link(SOURCES[source], reference)}</details></article>"""


def render_offices(sphere):
    options = "".join(
        f'<a href="?esfera={key}#cargos"'
        + (' aria-current="page"' if key == sphere else "")
        + f">{label}</a>"
        for key, label in {**SPHERES, "todos": "Todos os cargos"}.items()
    )
    cards = "".join(
        render_office_card(office) for office in OFFICES if sphere == "todos" or office[1] == sphere
    )
    return f"""<section id="cargos"><h2>Escolha os cargos que quer entender</h2>
<nav class="civic-filters" aria-label="Esfera dos cargos">{options}</nav>
{render_health_context()}
<div class="civic-offices">{cards}</div><p class="civic-key">Precisar de uma votação não significa
ter um chefe. Uma pessoa candidata ainda não exerce o cargo só por se candidatar.</p></section>"""


def render_law_flow(sphere):
    title, proposer, voter, executive, source = LAW_ROUTES[
        sphere if sphere != "todos" else "federal"
    ]
    steps = (
        ("Uma proposta", proposer),
        ("Análise e votação", voter),
        ("O governo responde", executive),
        (
            "A lei é publicada",
            (
                "A autoridade confirma a lei (promulgação) e o texto é divulgado oficialmente. "
                "As regras dizem quando começa a valer."
            ),
        ),
    )
    blocks = "".join(
        f'<li><span class="civic-step-number">{index}</span><h4>{name}</h4><p>{text(body)}</p></li>'
        for index, (name, body) in enumerate(steps, 1)
    )
    return f"""<section id="leis"><h2>Como uma ideia pode virar lei?</h2>
<p class="civic-flow-title">{title} · caminho geral de um projeto de lei</p>
<ol class="civic-law-flow">{blocks}</ol>
<p class="civic-return"><strong>Se houver veto:</strong> o projeto volta ao Legislativo.
Os parlamentares podem manter ou derrubar o veto, seguindo as regras. Derrubado o veto,
a lei é confirmada oficialmente (promulgada). Isso cabe ao presidente, governador
ou prefeito; se não o fizer no prazo, a direção do Legislativo assume nos casos previstos.</p>
<p>Comissões são grupos de deputados, senadores ou vereadores que estudam as propostas.
Algumas podem decidir sem reunir todos os integrantes da instituição.
Quem apresenta a ideia não escolhe sozinho o resultado. Se o Senado mudar um projeto federal
aprovado pela Câmara, ou o contrário,
as mudanças voltam à instituição que começou a análise.</p>
<p class="civic-key">Este caminho não vale para todas as normas. Por exemplo,
<strong>uma emenda constitucional não precisa de sanção do presidente.</strong></p>
{source_link(LAW_SOURCES[source])}</section>"""


def render_law_types():
    rows = []
    for title, explanation, proposer, voter, finalizer, qualification, source in LAW_TYPES:
        rows.append(f"""<details class="civic-law-type"><summary>{text(title)}</summary>
{render_law_description(title, explanation)}
<dl><dt>Quem propõe ou edita?</dt><dd>{text(proposer)}</dd>
<dt>Quem vota e aprova?</dt><dd>{text(voter)}</dd>
<dt>Como termina?</dt><dd>{text(finalizer)}</dd></dl><p>{text(qualification)}</p>
{source_link(LAW_SOURCES[source])}</details>""")
    return (
        """<section id="tipos"><h2>Nem toda regra segue o mesmo caminho</h2>
<p>Uma <strong>norma jurídica</strong> é uma regra oficial: pode dizer quais são nossos
direitos, deveres ou como o governo deve funcionar. Leis, decretos e resoluções são exemplos.
Cada tipo tem uma função e um jeito de ser criado. Abra o que quer entender.</p>"""
        + "".join(rows)
        + """
<details class="civic-law-type"><summary>Orçamento, decretos e outras regras</summary>
<p><strong>PPA, LDO e LOA:</strong> são leis de planejamento e orçamento. Presidente, governadores
e prefeitos apresentam os projetos de suas administrações. Deputados, senadores ou vereadores,
conforme a esfera, analisam, podem alterar dentro dos limites e votam. Há sanção ou veto.</p>
<p><strong>Exemplo ilustrativo:</strong> o PPA planeja ampliar a rede de saúde em quatro anos;
a LDO orienta as prioridades para o próximo orçamento; a LOA prevê quanto poderá ser gasto
naquele ano. Ter verba prevista não significa que a obra já foi executada.</p>
<p><strong>Decreto do Executivo:</strong> é editado pelo presidente, governador ou prefeito para
as finalidades permitidas. Em regra, regulamenta a lei; não serve para substituir qualquer lei.
As hipóteses constitucionais de decreto autônomo são restritas.</p>
<p><strong>Exemplo real:</strong> o Decreto 7.508/2011 detalhou a organização do SUS,
como as regiões de saúde. Ele ajuda a explicar como serviços de diferentes municípios
trabalham em rede. <a href="https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/decreto/d7508.htm"
target="_blank" rel="noopener noreferrer">Ver o decreto ↗</a></p>
<p>
<strong>Portarias e instruções:</strong> ministros, secretários estaduais ou municipais e dirigentes
de órgãos públicos podem editar esses atos para assuntos de sua responsabilidade.
Não passam, em regra, pelo mesmo rito de aprovação de uma lei.</p>
<p><strong>Exemplo real:</strong> a Portaria 2.436/2017 aprovou a Política Nacional de
Atenção Básica, com diretrizes para equipes e serviços como as UBS. É um exemplo de
regra do Ministério da Saúde.
<a href="https://bvsms.saude.gov.br/bvs/saudelegis/gm/2017/prt2436_22_09_2017.html"
target="_blank" rel="noopener noreferrer">Ver a portaria ↗</a></p>
<p>
<strong>Iniciativa popular</strong> é uma forma de apresentar projetos, não um tipo separado de
lei.
Tratados internacionais também têm um caminho próprio: participação do Executivo e, nos casos
previstos, aprovação do Congresso por decreto legislativo.</p>"""
        + source_link(SOURCES["constitution"], "arts. 49, 61, 84 e 165")
        + "</details></section>"
    )


def render_practice_and_glossary():
    glossary = "".join(
        f"<dt>{text(term)}</dt><dd>{text(description)}</dd>" for term, description in GLOSSARY
    )
    return (
        """<section id="pratique"><h2>Vamos ver se ficou claro?</h2>
<p>Pense na resposta antes de abrir. Você não precisa decorar nomes difíceis.</p>
<details><summary>Um vereador pode mandar consertar uma rua sozinho?</summary>
<p>Não. Ele pode cobrar a prefeitura, fiscalizar e propor medidas. A execução da obra pertence
ao Executivo, respeitando as leis e o orçamento.</p></details>
<details><summary>O governador é chefe do prefeito?</summary><p>Não. Estado e município têm
autonomia. Eles podem trabalhar juntos, mas isso não cria uma relação de chefia.</p></details>
<details>
<summary>Uma PEC aprovada precisa da assinatura do presidente para virar emenda?</summary>
<p>Não. Depois das aprovações exigidas nas duas Casas, as Mesas da Câmara e do Senado promulgam
a emenda. Não há sanção nem veto presidencial.</p></details></section>
<section id="palavras"><h2>Palavras que aparecem no caminho</h2><dl class="civic-glossary">"""
        + glossary
        + "</dl></section>"
    )


def render_civic_education(sphere="municipal"):
    if sphere not in {*SPHERES, "todos"}:
        raise PublicProfileError("INVALID_EDUCATION_SPHERE")
    intro = """<div class="civic-guide"><p class="eyebrow">GUIA PARA QUEM ESTÁ COMEÇANDO</p>
<h1>Quem faz o quê na política?</h1><p class="civic-lead">Entenda os cargos e o caminho das leis,
uma parte de cada vez.</p><nav class="civic-shortcuts" aria-label="Partes do guia">
<a href="#circulos">1. Veja os círculos</a><a href="#cargos">2. Escolha um cargo</a>
<a href="#leis">3. Siga uma lei</a><a href="#pratique">4. Teste o que entendeu</a></nav>
<aside class="civic-principle"><strong>Não é uma escada de chefes.</strong>
O presidente chefia o governo federal. Não é chefe dos governadores ou dos prefeitos.
O governo cuida dos serviços. O Legislativo vota regras e fiscaliza.
A Justiça julga conflitos. Cada um tem limites.</aside>"""
    content = intro + render_circle_section()
    content += render_government_map()
    content += render_offices(sphere) + render_law_flow(sphere)
    content += (
        render_law_types() + render_practice_and_glossary() + render_research_note() + "</div>"
    )
    return render_layout(
        "Quem faz o quê na política?",
        content,
        extra_stylesheet="/assets/civic-education.css",
        active_section="guide",
    )


def render_research_note():
    return """<details class="civic-research">
<summary>Fontes e como este guia foi desenhado</summary>
<p>Conteúdo jurídico revisado em 18/10/2026. É uma introdução: regras estaduais, leis orgânicas e
regimentos podem acrescentar etapas. Não é um catálogo de todos os atos administrativos
existentes.</p>
<p>O desenho usa partes curtas, rótulos junto das relações e perguntas com respostas para
consultar.
Essas escolhas são uma aplicação de estudos de aprendizagem; a compreensão deste guia por crianças
de 10 anos ainda não foi testada.</p><ul>
<li>
<a href="https://doi.org/10.1016/j.edurev.2015.12.003">Richter e colegas (2016): sinalização de
relações entre texto e imagem</a>.</li>
<li>
<a href="https://doi.org/10.1007/s10648-018-9456-4">Rey e colegas (2019): divisão do conteúdo em
partes</a>.</li>
<li>
<a href="https://www.psychologicalscience.org/journals/pspi/1529100612453266/">Dunlosky e
colegas (2013): prática de lembrar respostas</a>.</li>
<li>
<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC3932674/">Wing e colegas (2013): estudo de
neuroimagem sobre prática de recuperação</a>.</li>
</ul>
<p>Resultados variam conforme o público e o material. Estudos do cérebro não certificam esta
página
nem garantem o aprendizado. As perguntas acima ajudam a revisar, mas não substituem um teste de
compreensão com o público.</p></details>"""
