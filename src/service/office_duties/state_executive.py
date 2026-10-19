"""State-specific executive rules verified against the official São Paulo Constitution."""

from dataclasses import asdict

from service.office_duties.catalog import STATE_SOURCES, OfficeDuty, OfficialSource


def sao_paulo_executive_competencies(office_kind):
    reference = "art. 38" if office_kind == "vice_governor" else "art. 47, I a IV e XVII"
    source = OfficialSource(
        "Constituição do Estado de São Paulo", STATE_SOURCES["SP"].url, reference
    )
    if office_kind == "vice_governor":
        return [
            asdict(
                OfficeDuty(
                    "substitution_succession",
                    "Substituir e suceder o governador nas hipóteses legais",
                    "Substituição em impedimento e sucessão na "
                    "vaga dependem do fato jurídico correspondente.",
                    (source,),
                    scope="individual",
                )
            )
        ]
    return [
        asdict(
            OfficeDuty(
                "executive_direction",
                "Dirigir a administração estadual",
                "Exercer a direção superior com os secretários e representar o estado.",
                (source,),
                scope="individual",
            )
        ),
        asdict(
            OfficeDuty(
                "sanction_budget",
                "Atuar na legislação e no orçamento nas competências do Executivo",
                "Sancionar ou vetar projetos, regulamentar "
                "sua execução e encaminhar projetos orçamentários.",
                (source,),
                scope="individual",
            )
        ),
    ]


RJ_EXECUTIVE_URL = (
    "https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=2&url="
    "L2NvbnN0ZXN0Lm5zZi8xMTcxYzViYzU1Y2M4NjFiMDMyNTY4ZjUwMDcwY2ZiNi8xNzdhOWIyN2Y0"
    "NzY4NTM5MDMyNTY2N2EwMDYzNzMxMT9PcGVuRG9jdW1lbnQ%3D"
)
RJ_GOVERNMENT_URL = (
    "https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=73&url="
    "L2NvbnN0ZXN0Lm5zZi8xMTcxYzViYzU1Y2M4NjFiMDMyNTY4ZjUwMDcwY2ZiNi8xZWZkNjc4Mzlm"
    "N2NjYjA0MDMyNTY2N2EwMDYzNzMxMD9PcGVuRG9jdW1lbnQ%3D"
)


def rio_executive_competencies(office_kind):
    if office_kind == "vice_governor":
        source = OfficialSource(
            "Constituição do Estado do Rio de Janeiro",
            RJ_GOVERNMENT_URL,
            "art. 140, caput e parágrafo único",
        )
        return [
            asdict(
                OfficeDuty(
                    "substitution_succession",
                    "Substituir e suceder o governador nas hipóteses legais",
                    "Substituir em impedimento, suceder na vaga e auxiliar em missões especiais "
                    "quando convocado; demais atribuições dependem de lei complementar.",
                    (source,),
                    scope="individual",
                )
            )
        ]
    source = OfficialSource(
        "Constituição do Estado do Rio de Janeiro", RJ_EXECUTIVE_URL, "art. 145, II a V e XII"
    )
    return [
        asdict(
            OfficeDuty(
                "executive_direction",
                "Dirigir a administração estadual",
                "Exercer a direção superior com o auxílio dos secretários de estado.",
                (source,),
                scope="individual",
            )
        ),
        asdict(
            OfficeDuty(
                "sanction_budget",
                "Atuar na legislação e no orçamento nas competências do Executivo",
                "Sancionar ou vetar projetos, regulamentar leis "
                "e enviar planos e propostas orçamentárias.",
                (source,),
                scope="individual",
            )
        ),
    ]


def state_executive_competencies(office_kind, jurisdiction):
    if jurisdiction == "SP":
        return sao_paulo_executive_competencies(office_kind)
    return rio_executive_competencies(office_kind)
