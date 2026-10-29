"""Constantes e catálogos declarados do consolidador de evidências de políticas partidárias.

Linhagens de siglas são AGRUPAMENTO DE LEITURA declarado aqui, não identidade jurídica; temas medem
foco (saliência), não direção.
"""
# ruff: noqa: E501  # hardcode-ok: textos longos de fonte e prosa metodológica

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "data/political-orientation/party-model/policies"
DERIVED = POLICIES / "derived"
CPDOC_DIR = ROOT / "data/political-orientation/party-sources-1992-1994"
EXPERTS_CSV = ROOT / "data/political-orientation/sources/df_experts.csv"
POWER_ZUCCO_CSV = CPDOC_DIR / "power-zucco-2009-party-estimates.csv"
EXECUTIVE_EVIDENCE = (
    ROOT / "src/service/political_dashboard/executive_orientation_evidence.json"
)  # somente leitura

# id -> rótulos usados pela Câmara / pelo TSE / coluna dos especialistas (ano -> coluna) / linha Power-Zucco
LINEAGES = {
    "PT": (["PT"], ["PT"], {2018: "pt", 2022: "pt"}, "PT"),
    "PSDB": (["PSDB"], ["PSDB"], {2018: "psdb", 2022: "psdb"}, "PSDB"),
    "MDB": (["MDB*", "PMDB", "MDB"], ["PMDB", "MDB"], {2018: "mdb", 2022: "mdb"}, "PMDB"),
    "PFL_DEM_UNIAO": (
        ["PFL", "DEM", "UNIÃO"],
        ["PFL", "DEM", "UNIÃO"],
        {2018: "dem", 2022: "uniao"},
        "PFL",
    ),
    "PP_PPR_PPB": (
        ["PPR", "PPB", "PP", "PP**"],
        ["PPR", "PPB", "PP"],
        {2018: "progressistas", 2022: "progre"},
        "PPB",
    ),
    "PL_PR": (["PL", "PR", "PL*"], ["PL", "PR"], {2018: "pr", 2022: "pl"}, "PL"),
    "PTB": (["PTB"], ["PTB"], {2018: "ptb", 2022: "ptb"}, "PTB"),
    "PDT": (["PDT"], ["PDT"], {2018: "pdt", 2022: "pdt"}, "PDT"),
    "PSB": (["PSB"], ["PSB"], {2018: "psb", 2022: "psb"}, "PSB"),
    "PCdoB": (
        ["PCDOB", "PCdoB"],
        ["PC do B", "PCdoB"],
        {2018: "p_cdo_b", 2022: "p_cdo_b"},
        "PCDOB",
    ),
    "PSOL": (["PSOL"], ["PSOL"], {2018: "psol", 2022: "psol"}, None),
    "PSD": (["PSD"], ["PSD"], {2018: "psd", 2022: "psd"}, None),
    "REPUBLICANOS": (
        ["PRB", "REPUBLIC"],
        ["PRB", "REPUBLICANOS"],
        {2018: "prb", 2022: "rep"},
        None,
    ),
    "PODE": (["PTN", "PODE"], ["PTN", "PODE", "PODEMOS"], {2018: "pode", 2022: "podemos"}, None),
    "NOVO": (["NOVO"], ["NOVO"], {2018: "novo", 2022: "novo"}, None),
    "CIDADANIA_PPS": (
        ["PPS", "CIDADANIA"],
        ["PPS", "CIDADANIA"],
        {2018: "pps", 2022: "cdd"},
        "PPS",
    ),
    "PV": (["PV"], ["PV"], {2018: "pv", 2022: "pv"}, None),
    "REDE": (["REDE"], ["REDE"], {2018: "rede", 2022: "rede"}, None),
    "SOLIDARIEDADE": (
        ["SDD", "SD", "SOLIDARI"],
        ["SOLIDARIEDADE", "SD"],
        {2018: "sdd", 2022: "sdd"},
        None,
    ),
    "AVANTE": (["PTdoB", "AVANTE"], ["PT do B", "AVANTE"], {2018: "avante", 2022: "avante"}, None),
    "PRN": (["PRN"], ["PRN"], {}, "PRN"),
    "PDS": (["PDS"], ["PDS"], {}, None),
    "PSL": (["PSL"], ["PSL"], {2018: "psl"}, None),
}
PRESIDENT_PARTY_TO_LINEAGE = {
    "PT": "PT",
    "PSDB": "PSDB",
    "PMDB": "MDB",
    "MDB": "MDB",
    "PRN": "PRN",
    "PSL": "PSL",
}
NORMATIVE_GROUPS = {"projeto_de_lei", "projeto_de_lei_complementar", "emenda_constitucional"}
PERIODS = {
    "1987-1994": (1987, 1994),
    "1995-2002": (1995, 2002),
    "2003-2010": (2003, 2010),
    "2011-2018": (2011, 2018),
    "2019-2026": (2019, 2026),
}
MIN_PROPOSITIONS_PER_PERIOD = 100
MIN_PROPOSITIONS_PER_THEME = 15

# Mapeamento transparente tema oficial da Câmara -> indicador(es) da rubrica. Mede SALIÊNCIA, nunca direção.
THEME_TO_INDICATORS = {
    "Economia": ["E6", "E7"],
    "Finanças Públicas e Orçamento": ["E3", "E7"],
    "Indústria, Comércio e Serviços": ["E6", "E9"],
    "Trabalho e Emprego": ["E4"],
    "Previdência e Assistência Social": ["E2", "E5"],
    "Estrutura Fundiária": ["E8"],
    "Relações Internacionais e Comércio Exterior": ["E9", "C8"],
    "Energia, Recursos Hídricos e Minerais": ["E1", "E6"],
    "Agricultura, Pecuária, Pesca e Extrativismo": ["E8", "E6"],
    "Direito e Defesa do Consumidor": ["E6"],
    "Administração Pública": ["E1"],
    "Saúde": ["E2"],
    "Educação": ["E2"],
    "Direitos Humanos e Minorias": ["C1"],
    "Arte, Cultura e Religião": ["C2", "C3"],
    "Direito Penal e Processual Penal": ["C4"],
    "Defesa e Segurança": ["C4", "C5"],
    "Meio Ambiente e Desenvolvimento Sustentável": ["C7"],
}
DIMENSION_OF_PREFIX = {"E": "economica", "C": "sociocultural"}
SENTINELS = {"__total__", "__sem_tema_oficial__"}

DISCLAIMER = (
    "Temas medem FOCO (saliência), não direção: um projeto de 'Trabalho e Emprego' pode ampliar ou reduzir "
    "direitos. Direção só vem de política implementada, voto ou texto, com evidência própria."
)
