"""Plain-language office boundaries, distinct from a chain of governmental command."""

SOURCES = {
    "constitution": (
        "Constituição Federal",
        "https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm",
    ),
    "elections": (
        "TSE · atribuições dos cargos",
        (
            "https://www.tse.jus.br/comunicacao/noticias/2026/Setembro/"
            "faltam-21-dias-conheca-os-cargos-em-disputa-nas-eleicoes-2026"
        ),
    ),
    "municipal": (
        "TSE · prefeito e vereadores",
        (
            "https://www.tse.jus.br/comunicacao/noticias/2013/Janeiro/"
            "conheca-as-principais-atribuicoes-dos-prefeitos-e-vereadores"
        ),
    ),
    "state": ("ALESP · Poder Legislativo", "https://www.al.sp.gov.br/institucional/assembleia/"),
    "district": (
        "Câmara Legislativa do DF",
        "https://www.cl.df.gov.br/pt/web/guest/atividades-legislativas",
    ),
    "deputy": (
        "Câmara · papel do deputado federal",
        "https://www.camara.leg.br/noticias/545049-saiba-o-que-faz-um-deputado-federal",
    ),
    "senate": (
        "Senado · papel do senador",
        (
            "https://www12.senado.leg.br/noticias/materias/2022/08/05/"
            "voce-sabe-o-que-faz-um-senador-entenda-aqui"
        ),
    ),
}

# key, sphere, title, does, does not, relationships, source, reference
OFFICES = (
    (
        "councillor",
        "municipal",
        "Vereador e vereadora",
        "Propõe e vota normas municipais; fiscaliza a prefeitura e aprecia o orçamento na Câmara.",
        (
            "Não dirige secretarias nem executa obras por conta do mandato. Não "
            "aprova uma lei sozinho."
        ),
        (
            "Depende da votação dos demais vereadores. Projetos de lei aprovados "
            "seguem, em regra, ao prefeito para sanção ou veto; há matérias de "
            "proposta exclusiva do prefeito, como reajustes de servidores da prefeitura."
        ),
        "municipal",
        "CF, arts. 29 a 31",
    ),
    (
        "mayor",
        "municipal",
        "Prefeito e prefeita",
        (
            "Dirige a administração municipal, organiza serviços locais e executa "
            "políticas e orçamento."
        ),
        (
            "Não substitui a Câmara, não muda a Constituição e não comanda o "
            "governador ou o Judiciário."
        ),
        (
            "Depende de leis e orçamento aprovados pela Câmara para as medidas que "
            "exigem autorização. Coordena secretários municipais e presta contas."
        ),
        "municipal",
        "CF, arts. 29 a 31 e 37",
    ),
    (
        "vice_mayor",
        "municipal",
        "Vice-prefeito e vice-prefeita",
        (
            "Substitui ou sucede o prefeito nas hipóteses legais e exerce "
            "atribuições previstas localmente."
        ),
        "Não tem um governo paralelo nem voto de vereador por ser vice.",
        (
            "A atuação depende da Lei Orgânica e das funções legalmente atribuídas. "
            "Assumir a prefeitura é diferente de apenas ser vice."
        ),
        "constitution",
        "CF, art. 29; Lei Orgânica do município",
    ),
    (
        "state_deputy",
        "estadual",
        "Deputado e deputada estadual",
        (
            "Na Assembleia, propõe e vota normas estaduais, fiscaliza o governo "
            "estadual e delibera sobre o orçamento."
        ),
        (
            "Não administra a prefeitura, não executa serviços estaduais e não "
            "altera a Constituição Federal por voto individual."
        ),
        (
            "Depende da deliberação da Assembleia. Leis seguem, em regra, ao "
            "governador; emendas à Constituição estadual têm outro rito."
        ),
        "state",
        "CF, arts. 25 e 27; Constituição estadual",
    ),
    (
        "governor",
        "estadual",
        "Governador e governadora",
        (
            "Dirige a administração estadual e coordena políticas e serviços de "
            "responsabilidade do estado."
        ),
        "Não é chefe dos prefeitos, não substitui a Assembleia e não controla decisões judiciais.",
        (
            "Depende da Assembleia para leis e orçamento nas hipóteses previstas. "
            "Coordena secretários estaduais; coopera com União e municípios."
        ),
        "elections",
        "CF, arts. 25 e 28; Constituição estadual",
    ),
    (
        "vice_governor",
        "estadual",
        "Vice-governador e vice-governadora",
        (
            "Substitui ou sucede o governador e cumpre atribuições definidas pela "
            "Constituição estadual."
        ),
        (
            "Não possui, automaticamente, as mesmas competências do titular "
            "enquanto não estiver no exercício."
        ),
        "Depende das regras estaduais de substituição, sucessão e atribuição de funções.",
        "elections",
        "CF, art. 28; Constituição estadual",
    ),
    (
        "federal_deputy",
        "federal",
        "Deputado e deputada federal",
        (
            "Na Câmara, representa a população, delibera sobre normas federais e "
            "fiscaliza o Executivo federal."
        ),
        (
            "Não executa obras municipais nem transforma sua proposta em lei sem as "
            "etapas de aprovação."
        ),
        (
            "Depende da Câmara e, em regra, da revisão pelo Senado. Projetos de lei "
            "seguem à Presidência; há competências próprias de cada Casa."
        ),
        "deputy",
        "CF, arts. 44, 45, 48 a 51 e 65",
    ),
    (
        "senator",
        "federal",
        "Senador e senadora",
        (
            "Representa estados e DF; delibera sobre normas federais e exerce "
            "competências próprias do Senado, como apreciar certas indicações."
        ),
        "Não é superior ao deputado federal nem pode aprovar, sozinho, uma lei ou indicação.",
        (
            "Depende da deliberação do Senado; leis em geral também passam pela "
            "Câmara. Cada Casa tem competências exclusivas."
        ),
        "senate",
        "CF, arts. 46, 48, 49 e 52",
    ),
    (
        "president",
        "federal",
        "Presidente da República",
        (
            "É chefe de Estado e do Executivo federal. Dirige a administração "
            "federal, propõe medidas e sanciona ou veta projetos de lei."
        ),
        (
            "Não é chefe dos governadores, prefeitos, Congresso ou tribunais. Não "
            "pode ignorar a Constituição ou aprovar sozinho qualquer lei."
        ),
        (
            "Depende do Congresso para leis, orçamento e autorizações previstas. "
            "Coordena ministros; certas nomeações dependem de aprovação do Senado."
        ),
        "elections",
        "CF, arts. 76, 84 e 87",
    ),
    (
        "vice_president",
        "federal",
        "Vice-presidente da República",
        (
            "Substitui o presidente nos impedimentos, sucede em caso de vaga e "
            "auxilia em missões especiais."
        ),
        "Não dirige um segundo governo e não vota no Congresso por ocupar a Vice-Presidência.",
        (
            "A substituição e a sucessão seguem a Constituição. Missões de auxílio "
            "dependem de convocação do presidente."
        ),
        "constitution",
        "CF, art. 79",
    ),
    (
        "substitute",
        "federal",
        "Suplente parlamentar",
        (
            "Pode assumir o mandato nas hipóteses legais de convocação; no "
            "exercício, atua como parlamentar."
        ),
        "Não vota nem exerce o mandato apenas por constar como suplente.",
        (
            "Depende de convocação e posse conforme a Casa e a legislação. A "
            "suplência do Senado integra a chapa; a dos deputados segue o sistema "
            "eleitoral."
        ),
        "constitution",
        "CF, arts. 46, § 3º, e 56, § 1º",
    ),
    (
        "district_deputy",
        "distrital",
        "Deputado e deputada distrital",
        "Na Câmara Legislativa, delibera sobre normas do DF e fiscaliza o Executivo distrital.",
        (
            "Não é vereador de Brasília; o DF não se divide em municípios e tem "
            "competências estaduais e municipais."
        ),
        (
            "Depende da CLDF para aprovação. Projetos de lei seguem, em regra, ao "
            "governador do DF; a Lei Orgânica possui rito próprio."
        ),
        "district",
        "CF, art. 32; Lei Orgânica do DF",
    ),
    (
        "district_governor",
        "distrital",
        "Governador e vice do Distrito Federal",
        (
            "O governador dirige o Executivo distrital; o vice o substitui ou "
            "sucede nas hipóteses legais."
        ),
        (
            "Não existem prefeitos municipais no DF. Governador e vice não "
            "substituem as atribuições da CLDF."
        ),
        (
            "Leis e orçamento passam pela CLDF nas hipóteses previstas. A Lei "
            "Orgânica define as competências e a sucessão."
        ),
        "district",
        "CF, art. 32; Lei Orgânica do DF",
    ),
)
