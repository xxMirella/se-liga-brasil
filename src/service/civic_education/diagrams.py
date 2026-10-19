"""Visual office roles, shared responsibilities and proposal decisions."""

from pathlib import Path

from service.civic_education.health_cooperation import render_ubs_example
from service.civic_education.proposal_roles import render_proposal_roles

ASSETS = Path(__file__).parent / "assets"


def render_circle_section():
    offices = (ASSETS / "office-reach.svg").read_text(encoding="utf-8")
    responsibilities = (ASSETS / "shared-responsibilities.svg").read_text(encoding="utf-8")
    proposals = (ASSETS / "proposal-decisions.svg").read_text(encoding="utf-8")
    return f"""<section id="circulos" aria-labelledby="circle-title">
<h2 id="circle-title">O que cada cargo pode fazer?</h2>
<p>Veja <strong>quem atua</strong>, <strong>quem precisa trabalhar junto</strong>
e <strong>quem decide sobre uma proposta</strong>.</p>
<div class="civic-circle-pair">
<figure class="civic-circle-figure"><h3>1. Quem atua em cada esfera?</h3>{offices}
<figcaption><strong>Cada círculo reúne cargos que atuam naquela esfera.</strong>
Prefeitos, governadores e presidente administram. Vereadores, deputados e senadores
propõem regras, votam e fiscalizam, dentro de suas competências.</figcaption>
<p>As decisões podem afetar pessoas e atividades no município, no estado ou no país.
Um senador é eleito por um estado, mas vota leis que podem valer em todo o Brasil.</p>
<p class="civic-key">Os círculos não formam uma cadeia de chefes.
No DF, atuam o governador e os deputados distritais.</p></figure>
<figure class="civic-circle-figure"><h3>2. Quando precisam agir juntos?</h3>{responsibilities}
<figcaption><strong>Cooperação entre poderes, com tarefas diferentes.</strong>
Um propõe e executa; o outro vota e fiscaliza, conforme as regras.</figcaption>
{render_ubs_example()}</figure></div>
<figure class="civic-circle-figure civic-law-circles">
<div><h3>3. Quem propõe e quem vota?</h3>{proposals}</div>
<figcaption>{render_proposal_roles()}</figcaption></figure>
<details><summary>De onde vêm essas explicações?</summary><p>
<a href="https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm"
target="_blank" rel="noopener noreferrer">Constituição Federal, arts. 18, 23, 29 a 32,
44 a 52, 61 a 66 e 84</a>.</p><p>
<a href="https://www.saopaulo.sp.leg.br/camaraexplica/como-nascem-as-leis/"
target="_blank" rel="noopener noreferrer">Câmara de São Paulo · como nascem as leis</a>.
As regras locais e as competências de cada cargo precisam ser respeitadas.</p></details>
</section>"""
