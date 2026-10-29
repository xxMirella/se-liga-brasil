"""Curated thematic roll calls with an explicit, sourced direction for the "yes" vote.

Direction rule (never intuition, never how parties voted): each item names one indicator of
``data/political-orientation/party-model/rubric.json`` and says whether approving the
proposition moves toward the indicator's positive pole (+1: market, restriction, traditional or
authority side) or its negative pole (-1: state, redistribution, expansion of rights or
liberties). Poles and their sources are read from the rubric (status APROVADA_2026-10-29).
A guard keyword must appear in the official ementa, so a wrong number never enters silently.
"""

from dataclasses import dataclass

ECONOMIC = "economic"
SOCIOCULTURAL = "sociocultural"


@dataclass(frozen=True)
class ThematicItem:
    item_id: str
    theme: str
    indicator_id: str
    yes_sign: int  # +1: "yes" moves to the indicator's positive pole; -1: to the negative pole
    keys: tuple[
        tuple[str, str, int, str], ...
    ]  # (chamber, kind, number, year) as "camara"/"senado"
    ementa_guard: tuple[str, ...]  # at least one must appear in the official ementa
    rationale: str

    @property
    def dimension(self) -> str:
        return ECONOMIC if self.indicator_id.startswith("E") else SOCIOCULTURAL


def _keys(chamber: str, *refs: tuple[str, int, int]):
    return tuple((chamber, kind, number, year) for kind, number, year in refs)


CATALOG: tuple[ThematicItem, ...] = (
    ThematicItem(
        "teto_gastos_2016",
        "teto de gastos",
        "E7_fiscal_orthodoxy_public_spending",
        1,
        _keys("camara", ("PEC", 241, 2016)) + _keys("senado", ("PEC", 55, 2016)),
        ("regime fiscal",),
        "Cria teto ao gasto primario: polo positivo de E7.",
    ),
    ThematicItem(
        "reforma_trabalhista_2017",
        "reforma trabalhista",
        "E4_labor_regulation_unions",
        1,
        _keys("camara", ("PL", 6787, 2016)) + _keys("senado", ("PLC", 38, 2017)),
        ("consolida", "trabalho"),
        "Flexibiliza regras trabalhistas: polo positivo de E4.",
    ),
    ThematicItem(
        "terceirizacao_2015",
        "terceirizacao",
        "E4_labor_regulation_unions",
        1,
        _keys("camara", ("PL", 4330, 2004)) + _keys("senado", ("PLC", 30, 2015)),
        ("terceiriz", "terceiros"),
        "Amplia terceirizacao: flexibiliza regras (E4 +1).",
    ),
    ThematicItem(
        "terceirizacao_1998",
        "terceirizacao",
        "E4_labor_regulation_unions",
        1,
        _keys("camara", ("PL", 4302, 1998)),
        ("trabalho temporário", "terceiros"),
        "Amplia terceirizacao (E4 +1).",
    ),
    ThematicItem(
        "previdencia_2019",
        "reforma da previdencia",
        "E5_pension_policy_incidence",
        1,
        _keys("camara", ("PEC", 6, 2019)) + _keys("senado", ("PEC", 6, 2019)),
        ("previdência",),
        "Eleva exigencias e reduz beneficios gerais: E5 +1.",
    ),
    ThematicItem(
        "previdencia_2003",
        "reforma da previdencia",
        "E5_pension_policy_incidence",
        1,
        _keys("camara", ("PEC", 40, 2003)) + _keys("senado", ("PEC", 67, 2003)),
        ("previdência",),
        "Reduz beneficios do funcionalismo: E5 +1.",
    ),
    ThematicItem(
        "mp664_2014",
        "pensao por morte",
        "E2_social_spending_welfare_scope",
        1,
        _keys("camara", ("MPV", 664, 2014)),
        ("pensão", "previdência"),
        "Restringe beneficios: E2 +1.",
    ),
    ThematicItem(
        "mp665_2014",
        "seguro-desemprego",
        "E2_social_spending_welfare_scope",
        1,
        _keys("camara", ("MPV", 665, 2014)),
        ("seguro-desemprego", "abono"),
        "Restringe beneficios: E2 +1.",
    ),
    ThematicItem(
        "saneamento_2020",
        "marco do saneamento",
        "E1_state_ownership_privatization",
        1,
        _keys("camara", ("PL", 4162, 2019), ("PL", 3261, 2019))
        + _keys("senado", ("PL", 4162, 2019), ("PL", 3261, 2019)),
        ("saneamento",),
        "Abre o setor a concessao privada: E1 +1.",
    ),
    ThematicItem(
        "liberdade_economica_2019",
        "liberdade economica",
        "E6_market_regulation_competition",
        1,
        _keys("camara", ("MPV", 881, 2019)) + _keys("senado", ("PLV", 17, 2019)),
        ("liberdade econômica",),
        "Desregulamenta atividades economicas: E6 +1.",
    ),
    ThematicItem(
        "eletrobras_2021",
        "privatizacao da Eletrobras",
        "E1_state_ownership_privatization",
        1,
        _keys("camara", ("MPV", 1031, 2021)) + _keys("senado", ("PLV", 7, 2021)),
        ("eletrobras", "desestatiza"),
        "Desestatiza empresa: E1 +1.",
    ),
    ThematicItem(
        "ppp_2004",
        "parcerias publico-privadas",
        "E1_state_ownership_privatization",
        1,
        _keys("camara", ("PL", 2546, 2003)),
        ("parceria",),
        "Institui concessoes/PPPs com capital privado: E1 +1.",
    ),
    ThematicItem(
        "bolsa_familia_2003",
        "Bolsa Familia",
        "E2_social_spending_welfare_scope",
        -1,
        _keys("camara", ("MPV", 132, 2003)),
        ("bolsa", "programa"),
        "Cria programa de transferencia de renda: E2 -1.",
    ),
    ThematicItem(
        "mais_medicos_2013",
        "Mais Medicos",
        "E2_social_spending_welfare_scope",
        -1,
        _keys("camara", ("MPV", 621, 2013)),
        ("médicos",),
        "Expande servico publico: E2 -1.",
    ),
    ThematicItem(
        "pec_domesticas_2012",
        "direitos das domesticas",
        "E4_labor_regulation_unions",
        -1,
        _keys("camara", ("PEC", 478, 2010)) + _keys("senado", ("PEC", 66, 2012)),
        ("doméstic",),
        "Estende direitos trabalhistas: E4 -1.",
    ),
    ThematicItem(
        "pre_sal_partilha_2009",
        "pre-sal partilha",
        "E1_state_ownership_privatization",
        -1,
        _keys("camara", ("PL", 5938, 2009)) + _keys("senado", ("PLC", 7, 2010)),
        ("partilha",),
        "Reforca controle estatal do petroleo: E1 -1.",
    ),
    ThematicItem(
        "pre_sal_operadora_2016",
        "pre-sal Petrobras",
        "E1_state_ownership_privatization",
        1,
        _keys("camara", ("PL", 4567, 2016)) + _keys("senado", ("PLS", 131, 2015)),
        ("petrobras", "operador", "partilha"),
        "Retira exclusividade estatal: E1 +1.",
    ),
    ThematicItem(
        "irpf_isencao_2025",
        "isencao do IR e tributacao de altas rendas",
        "E3_progressive_taxation",
        -1,
        _keys("camara", ("PL", 1087, 2025)) + _keys("senado", ("PL", 1087, 2025)),
        ("imposto sobre a renda",),
        "Compensa isencao com tributo sobre altas rendas: E3 -1.",
    ),
    ThematicItem(
        "pec_transicao_2022",
        "PEC da Transicao",
        "E7_fiscal_orthodoxy_public_spending",
        -1,
        _keys("camara", ("PEC", 32, 2022)) + _keys("senado", ("PEC", 32, 2022)),
        ("responsabilidade", "despesa", "emenda constitucional"),
        "Excepciona gastos sociais do teto: E7 -1.",
    ),
    ThematicItem(
        "lrf_2000",
        "Lei de Responsabilidade Fiscal",
        "E7_fiscal_orthodoxy_public_spending",
        1,
        _keys("senado", ("PLC", 18, 1999), ("PLP", 18, 1999)),
        ("responsabilidade fiscal",),
        "Impoe regra restritiva de gasto: E7 +1.",
    ),
    ThematicItem(
        "cotas_universitarias_2008",
        "cotas universitarias",
        "C1_minority_rights_equality_policies",
        -1,
        _keys("camara", ("PL", 73, 1999)) + _keys("senado", ("PLC", 180, 2008)),
        ("ingresso", "universidades", "instituições federais"),
        "Politica afirmativa: C1 -1.",
    ),
    ThematicItem(
        "cotas_concursos_2023",
        "cotas em concursos",
        "C1_minority_rights_equality_policies",
        -1,
        _keys("camara", ("PL", 1958, 2021)) + _keys("senado", ("PL", 1958, 2021)),
        ("reserva", "vagas"),
        "Politica afirmativa: C1 -1.",
    ),
    ThematicItem(
        "maioridade_penal_1993",
        "maioridade penal",
        "C4_public_security_criminal_justice",
        1,
        _keys("camara", ("PEC", 171, 1993)),
        ("imputabilidade penal", "maioridade"),
        "Amplia punitivismo: C4 +1.",
    ),
    ThematicItem(
        "codigo_florestal_2011",
        "Codigo Florestal",
        "C7_environment_land_use",
        1,
        _keys("camara", ("PL", 1876, 1999)) + _keys("senado", ("PLC", 30, 2011)),
        ("florestal", "vegetação nativa", "áreas de preservação"),
        "Flexibiliza protecao ambiental: C7 +1.",
    ),
    ThematicItem(
        "marco_temporal_2023",
        "marco temporal",
        "C1_minority_rights_equality_policies",
        1,
        _keys("camara", ("PL", 490, 2007)) + _keys("senado", ("PL", 2903, 2023)),
        ("terras indígenas", "demarcação"),
        "Restringe direitos territoriais: C1 +1.",
    ),
    ThematicItem(
        "licenciamento_ambiental",
        "licenciamento ambiental",
        "C7_environment_land_use",
        1,
        _keys("camara", ("PL", 2159, 2021)) + _keys("senado", ("PL", 2159, 2021)),
        ("licenciamento",),
        "Afrouxa licenciamento: C7 +1.",
    ),
    ThematicItem(
        "agrotoxicos",
        "agrotoxicos",
        "C7_environment_land_use",
        1,
        _keys("camara", ("PL", 6299, 2002)) + _keys("senado", ("PL", 1459, 2022)),
        ("agrotóxicos", "pesticidas", "defensivos"),
        "Flexibiliza registro: C7 +1.",
    ),
    ThematicItem(
        "desarmamento_2003",
        "Estatuto do Desarmamento",
        "C5_firearms_access",
        -1,
        _keys("camara", ("PL", 1555, 2003)),
        ("armas", "desarmamento"),
        "Restringe acesso a armas: C5 -1.",
    ),
    ThematicItem(
        "armas_2019",
        "flexibilizacao de armas",
        "C5_firearms_access",
        1,
        _keys("camara", ("PL", 3723, 2019)) + _keys("senado", ("PL", 3723, 2019)),
        ("armas", "arma de fogo"),
        "Amplia acesso a armas: C5 +1.",
    ),
    ThematicItem(
        "lei_drogas_2013",
        "politica de drogas",
        "C4_public_security_criminal_justice",
        1,
        _keys("camara", ("PL", 7663, 2010)) + _keys("senado", ("PLC", 37, 2013)),
        ("drogas", "entorpecentes"),
        "Endurece politica de drogas: C4 +1.",
    ),
    ThematicItem(
        "pec_drogas_2023",
        "criminalizacao do porte de drogas",
        "C4_public_security_criminal_justice",
        1,
        _keys("camara", ("PEC", 45, 2023)) + _keys("senado", ("PEC", 45, 2023)),
        ("drogas", "entorpecentes"),
        "Criminaliza porte: C4 +1.",
    ),
    ThematicItem(
        "antiterrorismo_2015",
        "lei antiterrorismo",
        "C9_civil_liberties_institutional_checks",
        1,
        _keys("camara", ("PL", 2016, 2015)) + _keys("senado", ("PLC", 101, 2015)),
        ("terrorismo",),
        "Amplia poderes de Estado: C9 +1.",
    ),
    ThematicItem(
        "saidinha_2024",
        "saidinha",
        "C4_public_security_criminal_justice",
        1,
        _keys("camara", ("PL", 2253, 2022)) + _keys("senado", ("PL", 2253, 2022)),
        ("saída temporária", "execução penal"),
        "Restringe beneficios penais: C4 +1.",
    ),
    ThematicItem(
        "maria_da_penha_2006",
        "Lei Maria da Penha",
        "C1_minority_rights_equality_policies",
        -1,
        _keys("camara", ("PL", 4559, 2004)) + _keys("senado", ("PLC", 37, 2006)),
        ("violência doméstica",),
        "Amplia protecao de grupo vulneravel: C1 -1.",
    ),
    ThematicItem(
        "biosseguranca_2005",
        "pesquisa com celulas-tronco",
        "C2_moral_traditionalism_family_bodily_autonomy",
        -1,
        _keys("camara", ("PL", 2401, 2003)) + _keys("senado", ("PLC", 9, 2004)),
        ("biossegurança", "células-tronco"),
        "Liberaliza pesquisa: C2 -1.",
    ),
)

EXCLUDED_THEMES = {
    "autonomia do Banco Central (PLP 19/2019)": (
        "o rubric.json nao tem indicador para politica monetaria"
    ),
    "reforma tributaria (PEC 45/2019)": "sem direcao inequivoca em E3 (IVA e cashback)",
    "salario minimo": "votos sao sobre valores/indices, sem item unico de direcao",
    "aborto": "nenhuma votacao de merito nominal em plenario (apenas urgencia, PL 1904/2024)",
    "casamento/direitos LGBT": "nenhuma votacao de merito nominal em plenario encontrada",
    "impeachment 2016": "crime de responsabilidade, nao politica publica (N1, nao entra em E/C)",
}
