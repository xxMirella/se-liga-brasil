"""Identify each office's branch and institution without confusing executive secretariats."""

from service.public_profile_web.security import text

OFFICE_LOCATIONS = {
    "councillor": ("Legislativo", "Câmara Municipal", "Atua no município."),
    "mayor": (
        "Executivo",
        "Prefeitura",
        "Governa o município com as secretarias municipais; não é integrante da Câmara.",
    ),
    "vice_mayor": (
        "Executivo",
        "Vice-prefeitura / Prefeitura",
        "Atua no município, nas funções previstas e quando substitui o prefeito. "
        "Não é secretário automaticamente.",
    ),
    "state_deputy": ("Legislativo", "Assembleia Legislativa", "Atua no estado."),
    "governor": (
        "Executivo",
        "Governo do Estado",
        "Governa o estado com as secretarias estaduais; não é integrante da Assembleia.",
    ),
    "vice_governor": (
        "Executivo",
        "Vice-governadoria / Governo do Estado",
        "Atua no estado, nas funções previstas e quando substitui o governador. "
        "Não é secretário automaticamente.",
    ),
    "federal_deputy": (
        "Legislativo",
        "Câmara dos Deputados · Congresso Nacional",
        "Atua na esfera federal: suas decisões podem valer em todo o Brasil.",
    ),
    "senator": (
        "Legislativo",
        "Senado Federal · Congresso Nacional",
        "Representa um estado ou o DF, com atuação na esfera federal.",
    ),
    "president": (
        "Executivo",
        "Presidência da República",
        "Governa o país com os ministérios; não é integrante da Câmara ou do Senado.",
    ),
    "vice_president": (
        "Executivo",
        "Vice-Presidência da República",
        "Atua na esfera federal, nas funções previstas e quando substitui o presidente. "
        "Não é ministro automaticamente.",
    ),
    "district_deputy": (
        "Legislativo",
        "Câmara Legislativa do Distrito Federal",
        "Atua no Distrito Federal; não é a Câmara dos Deputados.",
    ),
    "district_governor": (
        "Executivo",
        "Governo do Distrito Federal",
        "Atua no DF com as secretarias distritais. O vice substitui o governador "
        "nas situações previstas; não há prefeito de Brasília.",
    ),
    "substitute": (
        "Legislativo · somente ao assumir o mandato",
        "Casa legislativa do mandato assumido",
        "Pode ser Câmara Municipal, Assembleia Legislativa, Câmara Legislativa do DF, "
        "Câmara dos Deputados ou Senado. Antes de assumir, não exerce o mandato.",
    ),
}


def render_office_location(office_key):
    branch, institution, explanation = OFFICE_LOCATIONS[office_key]
    return f"""<div class="civic-office-location">
<p><strong>Poder:</strong> {text(branch)}</p>
<p><strong>Onde atua:</strong> {text(institution)}</p>
<p class="civic-key">{text(explanation)}</p></div>"""
