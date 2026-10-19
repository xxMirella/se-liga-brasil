"""Explain legislative decisions across every elected sphere."""


def render_proposal_roles():
    return """<div id="quem-propoe-vota">
<p><strong>Propor é apresentar uma ideia. Votar é decidir em conjunto.</strong>
Sancionar é concordar com o projeto aprovado; vetar é rejeitar todo ou parte dele.</p>
<dl><dt><strong>Município</strong></dt>
<dd>Prefeito e vereadores podem propor projetos municipais.
Os vereadores votam na Câmara Municipal. O prefeito sanciona ou veta.</dd>
<dt><strong>Estado</strong></dt>
<dd>Governador e deputados estaduais podem propor projetos estaduais.
Os deputados estaduais votam na Assembleia Legislativa. O governador sanciona ou veta.</dd>
<dt><strong>Distrito Federal</strong></dt>
<dd>Governador do DF e deputados distritais podem propor projetos distritais.
Os deputados distritais votam na Câmara Legislativa. O governador do DF sanciona ou veta.</dd>
<dt><strong>Brasil</strong></dt>
<dd>Presidente, deputados federais e senadores podem propor projetos federais.
Em geral, deputados votam na Câmara dos Deputados e senadores no Senado:
as duas Casas precisam aprovar o mesmo texto. O presidente sanciona ou veta.</dd></dl>
<details><summary>E os vices e suplentes?</summary>
<p>Vice-prefeito, vice-governador (inclusive no DF) e vice-presidente não ganham voto
no Legislativo por serem vices. Quando assumem o cargo do titular, exercem as
competências daquele cargo. Suplentes só propõem e votam como parlamentares
quando assumem o mandato.</p></details>
<details><summary>Todo projeto segue esse caminho?</summary>
<p>Não. Este desenho mostra o caminho geral dos projetos de lei.
Por exemplo, o orçamento federal é proposto pelo presidente; o municipal, pelo prefeito.
O Legislativo também pode derrubar um veto, seguindo as regras de votação.</p>
<p>Uma PEC muda a Constituição: deputados federais e senadores precisam aprová-la
em dois turnos em cada Casa, com pelo menos três quintos dos votos.
Ela é promulgada pelas Mesas da Câmara e do Senado, sem sanção nem veto do presidente.</p>
<p>Cidadãos também podem apresentar projetos por iniciativa popular, cumprindo requisitos.
Órgãos como tribunais e Ministério Público têm iniciativa em assuntos previstos nas regras.</p>
</details><p>Ninguém aprova uma lei sozinho. Cada cargo atua nos assuntos permitidos
para sua esfera. O prefeito não vota como vereador; governadores e presidente
também não votam como parlamentares.</p>
<a href="#leis">Veja os tipos de lei e seus caminhos ↓</a></div>"""
