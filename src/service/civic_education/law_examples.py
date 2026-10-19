"""Link practical examples inside the same explanatory paragraph."""

from service.public_profile_web.security import text

LAW_EXAMPLE_LINKS = {
    "Lei ordinária": (("Lei 8.080/1990", "https://www.planalto.gov.br/ccivil_03/leis/l8080.htm"),),
    "Lei complementar": (
        ("Lei Complementar 150/2015", "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp150.htm"),
    ),
    "Emenda à Constituição Federal · PEC": (
        (
            "Emenda Constitucional 90/2015",
            "https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc90.htm",
        ),
        (
            "PEC 8/2025",
            "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2485341",
        ),
    ),
    "Medida provisória · MP": (
        (
            "MP 1.039/2021",
            "https://www.congressonacional.leg.br/materias/medidas-provisorias/-/mpv/147602",
        ),
    ),
    "Lei delegada": (
        ("Lei Delegada 13/1992", "https://www.planalto.gov.br/ccivil_03/leis/ldl/ldl13.htm"),
    ),
    "Decreto legislativo": (
        (
            "Decreto Legislativo 6/2020",
            "https://www.planalto.gov.br/ccivil_03/portaria/dlg6-2020.htm",
        ),
    ),
    "Resolução": (
        (
            "Resolução da Câmara 17/1989",
            "https://www2.camara.leg.br/legin/fed/rescad/1989/resolucaodacamaradosdeputados-17-21-setembro-1989-320110-norma-pl.html",
        ),
    ),
    "Constituição estadual e suas emendas": (
        (
            "Constituição de São Paulo",
            "https://www.al.sp.gov.br/repositorio/legislacao/constituicao/1989/compilacao-constituicao-0-05.10.1989.html",
        ),
    ),
    "Lei Orgânica municipal e suas emendas": (
        (
            "Lei Orgânica de São Paulo",
            "https://www.saopaulo.sp.leg.br/atividade-legislativa/lei-organica-do-municipio/",
        ),
    ),
    "Lei Orgânica do DF e suas emendas": (
        ("Lei Orgânica do DF", "https://www.cl.df.gov.br/lei-organica"),
    ),
}


def render_law_description(category, explanation):
    paragraph = text(explanation)
    for label, url in LAW_EXAMPLE_LINKS[category]:
        link = f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">{text(label)}</a>'
        paragraph = paragraph.replace(text(label), link, 1)
    return "<p>" + paragraph + "</p>"
