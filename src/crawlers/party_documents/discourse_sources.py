"""Documentary source candidates and literal search themes; no ideology inference."""

import re

PARTY_SOURCES: list[tuple[str, str, str]] = [
    (
        "PL",
        "programa",
        (
            "https://partidoliberal.org.br/wp-content/uploads/2022/06/pro"  # hardcode-ok: fonte
            "grama-do-partido-liberal.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PT",
        "manifesto",
        (
            "https://pt.org.br/construindo-o-futuro-manifesto-do-pt-para-"  # hardcode-ok: fonte
            "seguir-transformando-o-pais/"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "UNIAO",
        "manifesto",
        (
            "https://uniaobrasil.org.br/wp-content/uploads/2024/08/BOOK-1"  # hardcode-ok: fonte
            "48x210mm-Manifesto_Uniao_BRASIL.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PP",
        "programa",
        (
            "https://progressistas.org.br/programa-partidario/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "REPUBLICANOS",
        "programa",
        (
            "https://republicanos10.org.br/manifesto-e-programa/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PSB",
        "programa",
        (
            "https://www.autorreformapsb.com.br/wp-content/uploads/2022/0"  # hardcode-ok: fonte
            "7/Manifesto_e_Programa_do_PSB.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PSDB",
        "programa",
        (
            "https://www.psdb.org.br/conheca/programa/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PSOL",
        "programa",
        (
            "https://psol50.org.br/votepsol/programa-2026/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PCdoB",
        "programa",
        (
            "https://pcdob.org.br/programa/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PDT",
        "estatuto",
        (
            "https://www.pdt.org.br/wp-content/uploads/2020/07/EstatutoPD"  # hardcode-ok: fonte
            "T-alteracao_18-03-2019-Registrado.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PV",
        "programa",
        (
            "https://pv.org.br/opartido/programa/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "NOVO",
        "autodescricao_pagina",
        (
            "https://novo.org.br/noticias/por-que-ser-candidato-politico-"  # hardcode-ok: fonte
            "novo-2026-motivos/"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "REDE",
        "estatuto",
        (
            "https://redesustentabilidade.org.br/estatuto/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PSD",
        "autodescricao_pagina",
        (
            "https://psd.org.br/principios-e-valores/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "MISSAO",
        "estatuto",
        (
            "https://www.tse.jus.br/partidos/partidos-registrados-no-tse/"  # hardcode-ok: fonte
            "arquivos-1/estatuto-do-partido-formato-pdf-aprovado-em-4-11."
            "2025/%40%40display-file/file/estatuto-missao-deferido-pelo%2"
            "52520-tse-4-11-2025.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "MDB",
        "autodescricao_pagina",
        (
            "https://www.mdb.org.br/o-mdb-tem-hoje-uma-posicao-de-centro-"  # hardcode-ok: fonte
            "direita-na-economia-e-de-centro-esquerda-na-area-social-diz-"
            "presidente-baleia-rossi-sobre-novo-programa-do-partido/"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "MDB",
        "autodescricao_pagina",
        (
            "https://www.mdb.org.br/quem-somos/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PODE",
        "estatuto",
        (
            "https://www.podemos.org.br/wp-content/uploads/2024/10/TSE-es"  # hardcode-ok: fonte
            "tatuto-do-Podemos-de-30.9.2023-aprovado-23.5.2024.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PODE",
        "cartilha_posicionamento",
        (
            "https://podemos.org.br/wp-content/uploads/2021/09/CARTILHA-P"  # hardcode-ok: fonte
            "OSICIONAMENTO-AGOSTO21-SITE.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "AVANTE",
        "autodescricao_pagina",
        (
            "https://avante70.org.br/sobre-o-partido-avante/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "AVANTE",
        "estatuto",
        (
            "https://avante70.org.br/wp-content/uploads/2023/04/Estatuto_"  # hardcode-ok: fonte
            "Avante-70_2022-VERSAO-IMPRESSAO.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "SOLIDARIEDADE",
        "autodescricao_pagina",
        (
            "https://solidariedade.org.br/nossa-historia/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PRD",
        "autodescricao_pagina",
        (
            "https://prd25.org.br/quem-somos/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "PRD",
        "estatuto",
        (
            "https://prd25.org.br/wp-content/uploads/2024/05/ESTATUTO-PRD"  # hardcode-ok: fonte
            "-registrado-mai2024.pdf"
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "CIDADANIA",
        "programa",
        (
            "https://rede23.org/programa/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
    (
        "DC",
        "programa",
        (
            "https://www.democraciacrista.org.br/sobre-nos/programa/"  # hardcode-ok: fonte
        ),
    ),  # hardcode-ok: identidade documental pública
]


THEMES: dict[str, str] = {
    "economia_estado": (
        "economia|mercado|Estado|estatal|privatiza|propriedade|livre inici"
        "ativa|desenvolvimento|capitalis|socialis"
    ),
    "trabalho": r"trabalh|emprego|sindica|salário|CLT",
    "previdencia": r"previd[eê]ncia|aposenta",
    "tributacao": r"tribut|imposto|fiscal|carga",
    "educacao": r"educa[cç][aã]o|escola|universidade|ensino",
    "saude": r"sa[uú]de|SUS|hospital",
    "seguranca": r"seguran[cç]a p[uú]blica|violência|policial|armas|crime",
    "meio_ambiente": r"meio ambiente|ambiental|sustent|clima|ecolog",
    "costumes_valores": (
        "fam[ií]lia|religi|vida|g[eê]nero|aborto|diversidade|LGBT|cristã|tradi[cç]"
    ),
    "politica_externa": (
        "pol[ií]tica externa|soberania|internacional|Mercosul|integra[cç][aã]o|relações exteriores"
    ),
}


LABEL_PATTERN = re.compile(
    r"esquerda|direita|centro|socialis|liberal|social-democra|socialdemocra|conservador|"
    r"trabalhis|comunis|progressis|humanis|cristã|nacionalis",
    re.IGNORECASE,
)


ARTICLE_PATTERN = re.compile(r"Art(?:igo)?\.?\s*\d+[ºo°]?", re.IGNORECASE)


EXCERPTS_PER_THEME = 3


MAX_EXCERPT_CHARS = 420


ALL_PARTIES = [
    "AGIR",
    "AVANTE",
    "CIDADANIA",
    "DC",
    "MDB",
    "MISSAO",
    "MOBILIZA",
    "NOVO",
    "PCB",
    "PCO",
    "PCdoB",
    "PDT",
    "PL",
    "DEMOCRATA",
    "PODE",
    "PP",
    "PRD",
    "PRTB",
    "PSB",
    "PSD",
    "PSDB",
    "PSOL",
    "PSTU",
    "PT",
    "PV",
    "REDE",
    "REPUBLICANOS",
    "SOLIDARIEDADE",
    "UNIAO",
    "UP",
]
