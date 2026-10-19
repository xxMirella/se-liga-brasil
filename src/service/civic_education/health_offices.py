"""Concrete health impacts distinguish management, legislative oversight and substitution."""

from service.public_profile_web.security import text

HEALTH_IMPACTS = {
    "mayor": "Se a UBS municipal tem goteira ou falta equipe, a prefeitura pode organizar "
    "o reparo e a reposição de profissionais, seguindo as regras e o orçamento.",
    "councillor": "Se a UBS está sem manutenção, pode cobrar a prefeitura, pedir explicações "
    "e fiscalizar os gastos. Não é quem contrata a equipe ou executa o conserto.",
    "governor": "Pode melhorar hospitais estaduais, ampliar a oferta regional de exames "
    "e apoiar os municípios. Não assume o comando de toda UBS do estado.",
    "state_deputy": "Pode fiscalizar uma obra parada em hospital estadual e votar recursos "
    "para a saúde do estado. Não é quem compra o aparelho ou contrata o médico.",
    "district_governor": "Pode organizar reparos, equipes e equipamentos da rede pública do DF, "
    "por meio da Secretaria de Saúde. O vice exerce esses poderes quando assume o governo.",
    "district_deputy": "Pode cobrar a recuperação de uma UBS do DF e fiscalizar o orçamento "
    "da saúde. Não dirige a unidade nem contrata seus profissionais.",
    "president": "Pode organizar programas nacionais e repasses para apoiar unidades de saúde, "
    "além de cuidar da rede federal. Não administra cada UBS do país.",
    "federal_deputy": "Pode votar recursos federais para a saúde, propor emendas ao orçamento "
    "e fiscalizar repasses. Não manda contratar um médico para a UBS do bairro.",
    "senator": "Pode votar recursos e regras nacionais para a saúde e fiscalizar o governo "
    "federal. Não administra hospitais nem executa obras no estado que o elegeu.",
    "vice_mayor": "Pode acompanhar um projeto de melhoria de UBS se receber essa função. "
    "Ser vice, sozinho, não permite mandar na Secretaria de Saúde.",
    "vice_governor": "Pode acompanhar melhorias em hospitais se receber essa função. "
    "Não controla a rede estadual automaticamente por ser vice.",
    "vice_president": "Pode apoiar uma missão sobre saúde definida para sua atuação. "
    "Não pode liberar qualquer verba ou comandar o SUS só por ser vice.",
    "substitute": "Quando assume um mandato, pode fiscalizar a saúde e votar como "
    "parlamentar daquela esfera. Antes da posse, não tem esses poderes pelo cargo de suplente.",
}

# Each example names an action and the condition that makes it possible.
EXECUTIVE_EXAMPLES = {
    "mayor": (
        (
            "UBS, UPA e hospitais",
            "Planeja reformas e pode propor novas unidades municipais. "
            "Uma UPA é uma Unidade de Pronto Atendimento. Antes de atribuir uma falha ao prefeito, "
            "confira se a UPA ou o hospital é administrado pelo município.",
        ),
        (
            "Equipamentos e manutenção",
            "Na rede municipal, organiza compra, reparo e manutenção "
            "por meio da secretaria e dos responsáveis. Dinheiro e contratação "
            "precisam seguir as regras.",
        ),
        (
            "Mais profissionais",
            "Organiza a reposição de equipes municipais. "
            "Para contratar servidores, precisa observar cargos, orçamento e regras de ingresso.",
        ),
        (
            "Melhores salários",
            "Pode propor lei para melhorar salários de servidores do Executivo "
            "municipal. Depende da votação dos vereadores e de espaço legal no orçamento.",
        ),
        (
            "Verba e novos hospitais",
            "Propõe o orçamento e executa a parte aprovada para a saúde. "
            "Pode buscar apoio estadual ou federal. Um hospital novo também precisa de equipe, "
            "equipamentos e dinheiro contínuo para funcionar; só construir não basta.",
        ),
        (
            "Se há um problema",
            "Pode cobrar providências da secretaria e organizar a solução "
            "na rede municipal. Não pode furar regras de contratação nem comandar um "
            "hospital estadual.",
        ),
    ),
    "governor": (
        (
            "UBS, UPA e hospitais",
            "Pode planejar ampliação e construção na rede estadual e "
            "apoiar a rede municipal. Combina com municípios o acesso regional a "
            "exames e hospitais.",
        ),
        (
            "Equipamentos e manutenção",
            "Organiza compras, manutenção e reparos da rede estadual. "
            "A responsabilidade de cada UPA ou hospital depende de quem o administra.",
        ),
        (
            "Mais profissionais e melhores salários",
            "Planeja equipes estaduais e contratações "
            "legais. Pode propor reajustes para servidores do Executivo estadual, sujeitos à lei, "
            "à votação dos deputados estaduais e ao orçamento.",
        ),
        (
            "Disponibilização de verba",
            "Propõe o orçamento estadual, executa recursos aprovados "
            "e pode apoiar municípios conforme programas e acordos. Não é dinheiro "
            "pessoal do governador.",
        ),
        (
            "Se há um problema",
            "Pode determinar providências na administração estadual e "
            "articular apoio à prefeitura. Não é chefe do prefeito nem de toda UBS municipal.",
        ),
    ),
    "district_governor": (
        (
            "UBS, UPA e hospitais",
            "Planeja melhorias e novas unidades da rede do DF. "
            "Brasília não tem prefeito: a gestão pública de saúde é distrital.",
        ),
        (
            "Equipamentos e manutenção",
            "Organiza compra de aparelhos, reformas e manutenção "
            "na rede que administra, por meio da Secretaria de Saúde e dos gestores responsáveis.",
        ),
        (
            "Mais profissionais e melhores salários",
            "Planeja equipes e contratações legais. "
            "Pode propor reajustes para servidores do Executivo distrital; precisa de lei, "
            "votação dos deputados distritais e orçamento.",
        ),
        (
            "Disponibilização de verba",
            "Propõe o orçamento do DF e executa recursos aprovados. "
            "Pode articular apoio federal. Abrir unidade exige prever também o custo de mantê-la.",
        ),
        (
            "Se há um problema",
            "Pode cobrar soluções da Secretaria de Saúde na rede distrital. "
            "Não pode ignorar a Câmara Legislativa, a lei ou as regras de contratação. "
            "O vice atua nessas competências quando assume o governo.",
        ),
    ),
    "president": (
        (
            "UBS, UPA e hospitais",
            "Por meio do Ministério da Saúde, organiza políticas nacionais "
            "e programas que podem apoiar construção e melhoria de unidades. Também "
            "atua na rede federal.",
        ),
        (
            "Equipamentos e manutenção",
            "Pode organizar apoio federal para aparelhos e obras, "
            "conforme programas e requisitos. A manutenção de uma UBS municipal cabe "
            "à gestão local, "
            "mesmo que o aparelho tenha sido comprado com recurso federal.",
        ),
        (
            "Mais profissionais e melhores salários",
            "Pode organizar políticas de apoio às equipes "
            "e propor leis de sua competência. Contratações e reajustes da rede "
            "federal seguem regras "
            "próprias. Não define sozinho o salário de todo profissional municipal ou estadual.",
        ),
        (
            "Disponibilização de verba",
            "Envia a proposta de orçamento ao Congresso e executa "
            "repasses previstos nas regras. Anunciar apoio não significa que o "
            "dinheiro já foi pago.",
        ),
        (
            "Se há um problema",
            "Pode cobrar a gestão federal e articular apoio a estados e "
            "municípios. Não assume automaticamente a direção de uma UBS municipal.",
        ),
    ),
}

LEGISLATIVE_CONTEXT = {
    "councillor": ("municipal", "prefeitura", "vereadores"),
    "state_deputy": ("estadual", "governo estadual", "deputados estaduais"),
    "district_deputy": ("distrital", "governo do DF", "deputados distritais"),
    "federal_deputy": ("federal", "governo federal", "parlamentares do Congresso"),
    "senator": ("federal", "governo federal", "parlamentares do Congresso"),
}


def legislative_examples(office_key):
    sphere, executive, legislature = LEGISLATIVE_CONTEXT[office_key]
    return (
        (
            "Obras, aparelhos e manutenção",
            f"Pode fiscalizar gastos e atrasos da rede {sphere}, "
            f"pedir informações e cobrar o {executive}. Não executa obras nem escolhe "
            f"fornecedores.",
        ),
        (
            "Mais profissionais",
            "Pode cobrar explicações sobre falta de equipe e acompanhar "
            "medidas do governo. Não contrata médicos ou enfermeiros por exercer esse mandato.",
        ),
        (
            "Melhores salários",
            f"Participa das votações de leis e orçamento com os demais {legislature}, "
            "respeitando quem deve apresentar a proposta. Para reajustes de servidores do "
            "Executivo, por exemplo, ela parte do presidente, governador ou prefeito responsável. "
            "O parlamentar não aumenta sozinho o salário da "
            "equipe de uma UBS.",
        ),
        (
            "Disponibilização de verba",
            "Pode propor emendas ao orçamento conforme as regras "
            "e votar recursos com os demais parlamentares. A execução é do gestor responsável; "
            "uma emenda não prova que a obra foi feita ou que o dinheiro foi pago.",
        ),
        (
            "Se há um problema",
            f"Pode ouvir moradores, fiscalizar e cobrar o {executive}. "
            "Não pode usar o mandato para administrar a unidade ou interferir na "
            "ordem de atendimento.",
        ),
    )


def health_examples(office_key):
    if office_key in EXECUTIVE_EXAMPLES:
        return EXECUTIVE_EXAMPLES[office_key]
    if office_key in LEGISLATIVE_CONTEXT:
        return legislative_examples(office_key)
    if office_key == "substitute":
        return (
            (
                "Antes e depois de assumir",
                "Antes de assumir, pode encaminhar demandas como "
                "cidadão. Após a posse, atua com os poderes e limites do mandato que assumiu; "
                "não passa a administrar a unidade de saúde.",
            ),
        )
    return (
        (
            "Função recebida e substituição",
            "Pode acompanhar projetos e encaminhar demandas "
            "nas atribuições previstas nas regras ou recebidas do titular. Não tem comando "
            "independente para contratar equipes, aumentar salários ou liberar recursos. "
            "Ao assumir o cargo do titular, exerce suas competências e seus limites.",
        ),
    )


def render_health_examples(office_key):
    examples = "".join(
        f"<dt>{text(title)}</dt><dd>{text(description)}</dd>"
        for title, description in health_examples(office_key)
    )
    return f"""<div class="civic-health-impact"><p><strong>Exemplo na saúde</strong>
{text(HEALTH_IMPACTS[office_key])}</p>
<details class="civic-health-examples">
<summary>Na prática: unidades, equipes, salários e verbas</summary>
<dl>{examples}</dl><p>Exemplos de competências: não são obras ou resultados
comprovados de uma pessoa.</p>
<a href="#saude-regras">Entenda as regras e veja as fontes oficiais</a></details></div>"""


def render_health_context():
    return """<aside class="civic-note" id="saude-regras">
<p><strong>Vamos usar a saúde como exemplo: quem pode resolver cada problema?</strong>
A UBS é o posto de saúde, usado para consultas e acompanhamento.
A UPA atende urgências. Hospitais têm serviços como internações e cirurgias,
conforme sua estrutura. Eles trabalham em rede.</p>
<p><strong>Primeiro, descubra quem administra a unidade.</strong>
Nem toda UPA ou hospital é da prefeitura. A gestão pode ser municipal, estadual,
distrital ou federal; também há serviços contratados e outras formas de gestão.
Receber dinheiro de outro governo não muda automaticamente quem administra o local.</p>
<details><summary>Entenda contratações, salários e dinheiro da saúde</summary>
<p>Se falta profissional, é preciso verificar a equipe necessária, quem emprega,
as vagas e o dinheiro para pagar. Para servidores públicos, concurso é a regra,
com exceções previstas em lei; um político não pode simplesmente escolher qualquer pessoa.</p>
<p>Melhorar o salário de servidores exige lei específica, proposta de quem tem
competência e orçamento, respeitando os limites legais. Uma promessa ou um voto
isolado não aumenta o salário. Trabalhadores contratados por outras organizações
podem seguir regras de emprego diferentes.</p>
<p>Verba é dinheiro público previsto para uma finalidade. Anúncio, aprovação do orçamento,
repasse e pagamento são etapas diferentes. Para uma unidade nova funcionar, a obra
precisa vir acompanhada de equipamentos, profissionais e recursos para despesas contínuas.</p>
<p>Para cobrar uma solução, peça à direção da unidade ou à secretaria responsável:
qual é o problema, quem vai resolver, qual o prazo e se o recurso já chegou.</p>
<p>Fontes oficiais:
<a href="https://www.planalto.gov.br/ccivil_03/leis/l8080.htm" target="_blank"
rel="noopener noreferrer">Lei do SUS, arts. 9º e 16 a 18</a>;
<a href="https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/u/upa-24h" target="_blank"
rel="noopener noreferrer">Ministério da Saúde · UPA</a>;
<a href="https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm"
target="_blank" rel="noopener noreferrer">Constituição, arts. 37, 61, 165 a 169 e 198</a>.
Conteúdo educativo revisado em 18/10/2026.</p></details></aside>"""
