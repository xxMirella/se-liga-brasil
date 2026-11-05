"""Step 3 data (texts exactly as in the reference) and the shared glossary."""

# sphere: (adjective in "Lei <adjective> · caminho geral", proposal, vote, Executive answer)
LAW_ROUTES = {
    "municipal": (
        "da cidade",
        "Vereadores ou prefeito; a população também pode propor pelas regras locais.",
        "Vereadores analisam e votam na Câmara Municipal.",
        "O prefeito concorda (sanciona) ou veta.",
    ),
    "estadual": (
        "estadual",
        "Deputados estaduais ou governador; cidadãos, conforme a Constituição do estado.",
        "Deputados estaduais votam na Assembleia Legislativa.",
        "O governador sanciona ou veta.",
    ),
    "distrital": (
        "distrital",
        "Deputados distritais ou governador do DF.",
        "Deputados distritais votam na Câmara Legislativa.",
        "O governador do DF sanciona ou veta.",
    ),
    "federal": (
        "federal",
        "Deputados federais, senadores ou presidente; também cidadãos e alguns órgãos.",
        "Câmara dos Deputados e Senado precisam aprovar o mesmo texto.",
        "O presidente sanciona ou veta.",
    ),
}

LAW_PUBLICATION_STEP = (
    "A lei é promulgada e divulgada oficialmente. As regras dizem quando começa a valer."
)
LAW_VETO_ANSWER = (
    "O projeto volta ao Legislativo. Os parlamentares podem manter ou derrubar o veto, "
    "seguindo as regras. Derrubado o veto, a lei é promulgada."
)

# title, tag, who proposes, who approves, how it ends, example label, example url
LAW_NORMS = (
    (
        "Lei ordinária",
        "Tem sanção",
        "Parlamentares, chefe do Executivo, comissões e cidadãos com as assinaturas exigidas.",
        "O Legislativo da esfera, em geral por maioria dos presentes.",
        "O Executivo sanciona ou veta. Depois, a lei é promulgada e publicada.",
        "Lei 8.080/1990 · organiza o SUS",
        "https://www.planalto.gov.br/ccivil_03/leis/l8080.htm",
    ),
    (
        "Lei complementar",
        "Tem sanção",
        "Os mesmos autores da lei ordinária.",
        "Mais da metade de todos os integrantes da Casa.",
        "O Executivo sanciona ou veta.",
        "LC 150/2015 · emprego doméstico",
        "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp150.htm",
    ),
    (
        "Emenda à Constituição · PEC",
        "Sem sanção",
        "Presidente; 1/3 dos deputados ou dos senadores; ou mais da metade das Assembleias.",
        "Câmara e Senado, em dois turnos cada, com 3/5 dos votos.",
        "As Mesas da Câmara e do Senado promulgam. O presidente não sanciona nem veta.",
        "EC 90/2015 · transporte como direito social",
        "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc90.htm",
    ),
    (
        "Medida provisória · MP",
        "Só se mudar",
        "O presidente publica, com relevância e urgência. Já vale antes da votação.",
        "Deputados e senadores decidem se vira lei.",
        "Se o texto for mantido, o Congresso promulga. Se mudar, vai à sanção ou veto.",
        "MP 1.039/2021 · Auxílio Emergencial",
        "https://www.congressonacional.leg.br/materias/medidas-provisorias/-/mpv/147602",
    ),
    (
        "Lei delegada",
        "Presidente edita",
        "O presidente pede autorização ao Congresso.",
        "Deputados e senadores aprovam a autorização e seus limites.",
        "O presidente escreve e promulga a lei dentro da autorização.",
        "Lei Delegada 13/1992",
        "https://www.planalto.gov.br/ccivil_03/leis/ldl/ldl13.htm",
    ),
    (
        "Decreto legislativo",
        "Sem sanção",
        "Parlamentares e comissões, conforme o assunto.",
        "O Legislativo da esfera.",
        "A presidência do Legislativo promulga.",
        "DL 6/2020 · calamidade da pandemia",
        "https://www.planalto.gov.br/ccivil_03/portaria/dlg6-2020.htm",
    ),
    (
        "Resolução",
        "Sem sanção",
        "Parlamentares, comissões ou Mesa da Casa.",
        "A própria Casa que decide.",
        "O presidente da Casa promulga.",
        "Resolução da Câmara 17/1989 · regimento",
        (
            "https://www2.camara.leg.br/legin/fed/rescad/1989/"
            "resolucaodacamaradosdeputados-17-21-setembro-1989-320110-norma-pl.html"
        ),
    ),
)

# Sources line of the step, as in the reference.
LAW_SOURCE_LINKS = (
    ("Câmara · como nascem as normas", "https://www.camara.leg.br/entenda-o-processo-legislativo/"),
    (
        "Câmara de São Paulo · como nascem as leis",
        "https://www.saopaulo.sp.leg.br/camaraexplica/como-nascem-as-leis/",
    ),
)

GLOSSARY = (
    (
        "Norma jurídica",
        "Uma regra oficial sobre direitos, deveres ou funcionamento do poder público. "
        "Leis, decretos e resoluções são exemplos; cada tipo tem sua função e suas regras.",
    ),
    ("Propor", "Apresentar uma ideia escrita. Ainda não é uma lei aprovada."),
    (
        "Comissão",
        (
            "Um grupo de parlamentares que examina um assunto. Em certos casos, "
            "pode decidir sem votação no Plenário."
        ),
    ),
    (
        "Votar e aprovar",
        (
            "Parlamentares dão seus votos. A proposta só passa se alcançar a "
            "quantidade de votos exigida."
        ),
    ),
    (
        "Sanção",
        (
            "O presidente, governador ou prefeito concorda com um projeto de lei aprovado. Em "
            "algumas situações, o silêncio no prazo legal também vale como sanção."
        ),
    ),
    (
        "Veto",
        (
            "O presidente, governador ou prefeito rejeita todo ou parte de um projeto, com "
            "justificativa. O Legislativo pode reexaminar essa rejeição."
        ),
    ),
    (
        "Promulgação",
        (
            "É a confirmação oficial de que a lei ou emenda foi criada. Conforme o tipo, "
            "cabe ao presidente, governador, prefeito ou à direção da Câmara, Senado ou "
            "Assembleia. É diferente de votar e de sancionar."
        ),
    ),
    (
        "Publicação e vigência",
        (
            "A norma é divulgada oficialmente. Começa a valer na data ou no prazo "
            "que as regras aplicáveis determinarem."
        ),
    ),
    (
        "Quórum",
        "A quantidade de pessoas ou votos necessária para uma decisão. Não é sempre a mesma.",
    ),
)
