"""Explicit browser-reviewed evidence when an official host rejects automated downloads."""

from hashlib import sha256

BOLSONARO_SOURCE_URL = (
    "https://agenciabrasil.ebc.com.br/politica/noticia/2021-11/"
    "presidente-bolsonaro-assina-filiacao-ao-pl"
)
MDB_SOURCE_URL = (
    "https://www.tse.jus.br/comunicacao/noticias/2018/Maio/"
    "aprovada-mudanca-do-nome-do-partido-do-movimento-democratico-brasileiro-pmdb"
)
BOLSONARO_TRANSCRIPTION = (
    "O presidente Jair Bolsonaro se filiou hoje (30) ao Partido Liberal (PL). "
    "Eleito em 2018 pelo PSL, Bolsonaro deixou o partido em novembro de 2019 "
    "e não estava filiado a nenhum partido."
)
MDB_TRANSCRIPTION = (
    "15/05/2018: o TSE aprovou a mudança do nome e da sigla do Partido do Movimento "
    "Democrático Brasileiro (PMDB) para Movimento Democrático Brasileiro (MDB)."
)
DELFIM_SOURCE_URL = (
    "https://bndigital.bn.gov.br/artigos/"
    "acervo-da-bn-a-gazeta-vida-e-morte-de-um-vespertino-paulistano/"
)
DELFIM_TRANSCRIPTION = (
    "Delfim Moreira assumiu seu lugar por menos de um ano, até o início do mandato de "
    "Epitácio Pessoa, do mesmo PRM de Moreira, que durou de 1919 a 1922."
)
VARGAS_UNESP_SOURCE_URL = (
    "https://periodicos.fclar.unesp.br/estudos/article/download/13979/9355/42921"
)
VARGAS_UNESP_TRANSCRIPTION = (
    "ininterruptos (1930-1945), durante o qual Getúlio Vargas governou sem partido"
)
ARENA_REGISTRATION_SOURCE_URL = (
    "https://www.tse.jus.br/partidos/partidos-registrados-no-tse/historico/"
    "registros-de-partidos-politicos-1945-a-1979-1/alianca-renovadora-nacional"
)
ARENA_REGISTRATION_TRANSCRIPTION = (
    "Data: 24.03.1966; deferir o registro da Aliança Renovadora Nacional (ARENA). "
    "Data: 07.03.1967; transformação em partido político"
)


def reviewed_evidence(url, transcription, *, published_on, reviewed_on="2026-10-23"):
    return {
        "url": url,
        "source_type": "reviewed_official_transcription",
        "reviewed_on": reviewed_on,
        "source_published_on": published_on,
        "acquisition_limitation": "official_server_rejected_automated_download_http_403",
        "sha256_scope": "reviewed_transcription",
        "original_document_sha256": None,
        "reviewed_transcription_sha256": sha256(transcription.encode()).hexdigest(),
        "locator": transcription,
    }


def reviewed_party_transcriptions():
    return {
        ARENA_REGISTRATION_SOURCE_URL: {
            "transcription": ARENA_REGISTRATION_TRANSCRIPTION,
            "evidence": reviewed_evidence(
                ARENA_REGISTRATION_SOURCE_URL, ARENA_REGISTRATION_TRANSCRIPTION,
                published_on=None, reviewed_on="2026-10-24",
            ) | {
                "publisher": "Tribunal Superior Eleitoral",
                "source_sections": ["Resolução TSE nº 7.823", "Resolução TSE nº 8.097"],
            },
        },
        VARGAS_UNESP_SOURCE_URL: {
            "transcription": VARGAS_UNESP_TRANSCRIPTION,
            "evidence": reviewed_evidence(
                VARGAS_UNESP_SOURCE_URL, VARGAS_UNESP_TRANSCRIPTION,
                published_on="2020-07-24", reviewed_on="2026-10-24",
            ) | {
                "source_type": "reviewed_academic_article_transcription",
                "publisher": "UNESP / Estudos de Sociologia", "author": "Lucila Scavone",
                "page_label": "194", "doi": "10.52780/res.13979",
                "acquisition_limitation": (
                    "publisher_server_returned_maintenance_page_original_text_reviewed_in_web_index"
                ),
            },
        },
        DELFIM_SOURCE_URL: {
            "transcription": DELFIM_TRANSCRIPTION,
            "evidence": reviewed_evidence(
                DELFIM_SOURCE_URL, DELFIM_TRANSCRIPTION,
                published_on=None, reviewed_on="2026-10-24",
            ) | {"publisher": "Fundação Biblioteca Nacional / BNDigital"},
        },
        BOLSONARO_SOURCE_URL: {
            "transcription": BOLSONARO_TRANSCRIPTION,
            "evidence": reviewed_evidence(
                BOLSONARO_SOURCE_URL, BOLSONARO_TRANSCRIPTION, published_on="2021-11-30"
            ),
        },
        "pmdb_mdb_name_change": reviewed_evidence(
            MDB_SOURCE_URL, MDB_TRANSCRIPTION, published_on="2018-05-15"
        ),
    }
