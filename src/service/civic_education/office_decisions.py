"""Separate presenting, voting, sanctioning and the people affected by each office."""

# proposal, legislative vote or executive decision, reach
OFFICE_DECISIONS = {
    "councillor": (
        "Sim. Pode apresentar projetos de lei municipal nos assuntos permitidos.",
        "Sim. Vota projetos e o orçamento com os outros vereadores. "
        "A aprovação depende dos votos exigidos; um vereador não aprova sozinho.",
        "As leis aprovadas podem atingir pessoas e atividades em todo o município, "
        "ou uma situação local prevista no texto. Não são só para quem votou nele.",
    ),
    "mayor": (
        "Sim. Envia projetos de lei aos vereadores. "
        "Também apresenta o orçamento: o plano de uso do dinheiro do município.",
        "Não vota como vereador na Câmara. Depois da votação dos vereadores, "
        "pode concordar com o projeto (sancionar) ou rejeitá-lo (vetar), conforme o caso.",
        "Pessoas que moram, trabalham ou usam os serviços do município. "
        "Por exemplo: crianças atendidas em creches e pessoas que usam ruas e serviços locais.",
    ),
    "vice_mayor": (
        "Ser vice, por si só, não dá o mesmo poder de apresentar projetos do prefeito. "
        "Ao assumir a prefeitura, exerce as competências do cargo.",
        "Não vota como vereador por ser vice. Se assumir como prefeito, "
        "atua como Executivo, não como integrante da Câmara.",
        "Sua atuação no Executivo pode afetar a população do município, "
        "conforme a função que estiver exercendo.",
    ),
    "state_deputy": (
        "Sim. Pode apresentar projetos estaduais nos assuntos permitidos.",
        "Sim. Vota projetos e o orçamento com os outros deputados estaduais. "
        "Não aprova sozinho.",
        "As normas estaduais podem atingir pessoas e atividades no estado, "
        "não apenas na cidade em que recebeu votos.",
    ),
    "governor": (
        "Sim. Envia projetos estaduais e o orçamento aos deputados estaduais.",
        "Não vota como deputado na Assembleia. Pode sancionar ou vetar "
        "projetos de lei aprovados pelos deputados, conforme o caso.",
        "Pessoas que vivem no estado ou usam seus serviços, como a rede estadual de ensino. "
        "A medida concreta define quem é atendido ou afetado.",
    ),
    "vice_governor": (
        "Ser vice não dá automaticamente todas as competências do governador. "
        "Ao assumir o governo, exerce as competências do cargo.",
        "Não vota como deputado estadual por ser vice. "
        "Quando assume o governo, atua como Executivo.",
        "Sua atuação pode afetar pessoas e serviços do estado, "
        "conforme as funções que exercer.",
    ),
    "federal_deputy": (
        "Sim. Pode apresentar projetos federais nos assuntos permitidos.",
        "Sim. Vota na Câmara com os outros deputados federais. "
        "Em geral, o projeto também precisa da aprovação dos senadores.",
        "Leis federais podem atingir pessoas e atividades em todo o Brasil, "
        "não apenas no estado pelo qual foi eleito.",
    ),
    "senator": (
        "Sim. Pode apresentar projetos federais nos assuntos permitidos.",
        "Sim. Vota no Senado com os outros senadores. "
        "Em geral, o projeto também precisa da aprovação dos deputados federais.",
        "Representa um estado ou o DF, mas vota leis que podem valer em todo o Brasil. "
        "Não decide só para as pessoas do seu estado.",
    ),
    "president": (
        "Sim. Envia projetos federais e o orçamento ao Congresso. "
        "Também pode editar medidas provisórias dentro das regras próprias.",
        "Não vota como deputado ou senador. Pode sancionar ou vetar projetos de lei "
        "aprovados no Congresso. Não sanciona nem veta emendas à Constituição.",
        "As ações do governo federal e as normas federais podem afetar "
        "pessoas e atividades em todo o Brasil.",
    ),
    "vice_president": (
        "Ser vice não dá automaticamente todas as competências do presidente. "
        "Quando assume a Presidência, exerce as competências do cargo.",
        "Não vota no Congresso por ser vice. "
        "Quando assume a Presidência, atua como Executivo.",
        "Pode atuar em missões de alcance nacional ou, ao assumir, "
        "nas responsabilidades do governo federal.",
    ),
    "substitute": (
        "Somente ao assumir o mandato pode atuar como parlamentar e "
        "apresentar projetos dentro das competências daquele cargo.",
        "Somente ao assumir o mandato pode votar como parlamentar. "
        "A condição de suplente, sozinha, não dá voto.",
        "O alcance depende do mandato assumido. No Congresso, por exemplo, "
        "as leis federais podem valer em todo o Brasil.",
    ),
    "district_deputy": (
        "Sim. Pode apresentar projetos distritais nos assuntos permitidos.",
        "Sim. Vota leis e o orçamento com os outros deputados distritais na CLDF, "
        "a Câmara Legislativa do Distrito Federal.",
        "As normas distritais podem atingir pessoas e atividades no Distrito Federal.",
    ),
    "district_governor": (
        "O governador pode enviar projetos e o orçamento aos deputados distritais. "
        "O vice exerce essas competências quando assume o governo.",
        "O governador não vota como deputado distrital. Pode sancionar ou vetar "
        "projetos de lei aprovados na Câmara Legislativa, conforme o caso.",
        "Pessoas que vivem no DF ou usam seus serviços. "
        "Não se trata de um governo municipal de Brasília.",
    ),
}
