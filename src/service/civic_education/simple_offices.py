"""First reading layer: concrete short explanations before legal detail."""

# does, does not, needs
SIMPLE_OFFICES = {
    "councillor": (
        "Discute regras da cidade e fiscaliza a prefeitura.",
        "Não executa obras nem comanda os serviços da prefeitura.",
        "Dos outros vereadores, que formam a Câmara Municipal, para aprovar regras.",
    ),
    "mayor": (
        "Organiza serviços municipais. Na saúde, planeja equipes, manutenção e melhorias "
        "da rede municipal por meio da Secretaria de Saúde.",
        "Não vota no lugar dos vereadores nem aprova leis sozinho.",
        "Dos vereadores, que formam a Câmara Municipal, para votar leis e o orçamento.",
    ),
    "vice_mayor": (
        "Ajuda e pode substituir o prefeito, conforme as regras.",
        "Não governa a cidade em paralelo ao prefeito.",
        "Das regras da cidade para saber quando assume.",
    ),
    "state_deputy": (
        "Discute regras do estado e fiscaliza o governo estadual.",
        "Não é quem dirige os serviços do estado.",
        "Dos outros deputados estaduais, que formam a Assembleia Legislativa.",
    ),
    "governor": (
        "Organiza serviços estaduais. Na saúde, planeja melhorias em hospitais estaduais "
        "e o acesso regional a exames e atendimento.",
        "Não vota na Assembleia nem é chefe dos prefeitos.",
        "Dos deputados estaduais, na Assembleia Legislativa, para votar leis e o orçamento.",
    ),
    "vice_governor": (
        "Pode substituir o governador nas situações previstas.",
        "Não manda no estado só por ser vice.",
        "Das regras do estado para saber quando assume.",
    ),
    "federal_deputy": (
        "Discute regras do país e fiscaliza o governo federal.",
        "Não pode transformar sua ideia em lei sozinho.",
        "Dos deputados federais, na Câmara, e em geral dos senadores, no Senado.",
    ),
    "senator": (
        "Representa seu estado ou o DF e vota regras do país.",
        "Não é chefe dos deputados.",
        "Dos outros senadores e, em geral, dos deputados federais, na Câmara.",
    ),
    "president": (
        "Dirige o governo federal. Na saúde, organiza políticas nacionais e apoio financeiro "
        "por meio do Ministério da Saúde, além da atuação na rede federal.",
        "Não vota no Congresso nem é chefe dos governadores, prefeitos ou deputados.",
        "Dos deputados federais e senadores, que formam o Congresso Nacional.",
    ),
    "vice_president": (
        "Substitui ou sucede o presidente nas situações previstas.",
        "Não governa o país em paralelo ao presidente.",
        "Das regras da Constituição para assumir a Presidência.",
    ),
    "substitute": (
        "Pode assumir uma vaga no Legislativo quando for convocado.",
        "Não vota antes de assumir o mandato.",
        "Da convocação e da posse conforme as regras.",
    ),
    "district_deputy": (
        "Discute regras do DF e fiscaliza seu governo.",
        "Não existe vereador de Brasília para dividir esse papel.",
        "Dos outros deputados distritais, que formam a Câmara Legislativa do DF.",
    ),
    "district_governor": (
        "O governador cuida do governo do DF; o vice pode substituí-lo.",
        "Não substituem as decisões da Câmara Legislativa.",
        "Dos deputados distritais, na Câmara Legislativa do DF, para votar leis e orçamento.",
    ),
}
