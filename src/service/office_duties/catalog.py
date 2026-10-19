"""Small reviewed catalog; institutional powers are not individual performance targets."""

from dataclasses import dataclass
from datetime import date

CATALOG_VERSION = "2026-10-18.1"
REVIEWED_ON = date(2026, 10, 18)
FEDERAL_CONSTITUTION_URL = (
    "https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm"
)


@dataclass(frozen=True)
class OfficialSource:
    title: str
    url: str
    reference: str


@dataclass(frozen=True)
class OfficeDuty:
    code: str
    title: str
    description: str
    sources: tuple[OfficialSource, ...]
    scope: str = "collective_institution"


@dataclass(frozen=True)
class OfficeDutyCatalog:
    office_kind: str
    jurisdiction: str
    items: tuple[OfficeDuty, ...]
    limitations: tuple[str, ...] = ()


def constitutional_source(reference: str) -> OfficialSource:
    return OfficialSource(
        "Constituição Federal — texto compilado", FEDERAL_CONSTITUTION_URL, reference
    )


FEDERAL_LEGISLATION = OfficeDuty(
    "legislation",
    "Legislar no âmbito federal",
    "Debater e votar matérias da União, respeitando iniciativa reservada e o processo legislativo.",
    (constitutional_source("arts. 48 e 61"),),
)
FEDERAL_OVERSIGHT = OfficeDuty(
    "oversight",
    "Fiscalizar o Executivo federal",
    "Participar do controle dos atos do Executivo "
    "e dos recursos públicos, pelos instrumentos legais.",
    (constitutional_source("arts. 49, X, 50 e 70"),),
)
FEDERAL_BUDGET = OfficeDuty(
    "budget",
    "Deliberar sobre o orçamento federal",
    "Examinar e votar planejamento e orçamento, dentro das competências do Congresso.",
    (constitutional_source("art. 166"),),
)
SENATE_AUTHORITIES = OfficeDuty(
    "authorities",
    "Deliberar sobre autoridades e operações financeiras",
    "Apreciar indicações de autoridades e operações "
    "financeiras nos casos previstos na Constituição.",
    (constitutional_source("art. 52, III a IX"),),
)
STATE_SOURCES = {
    "SP": OfficialSource(
        "Constituição do Estado de São Paulo — texto compilado",
        "https://www.al.sp.gov.br/repositorio/legislacao/constituicao/1989/"
        "compilacao-constituicao-0-05.10.1989.html",
        "arts. 19, 20, 24 e 32",
    ),
    "RJ": OfficialSource(
        "ALERJ — papel do deputado estadual",
        "https://www.alerj.rj.gov.br/Visualizar/Noticia/86976",
        "Síntese institucional das funções de legislar, fiscalizar e representar",
    ),
}


def state_catalog(jurisdiction: str) -> OfficeDutyCatalog:
    source = STATE_SOURCES[jurisdiction]
    return OfficeDutyCatalog(
        "state_deputy",
        jurisdiction,
        (
            OfficeDuty(
                "legislation",
                "Legislar no âmbito estadual",
                "Debater e votar matérias estaduais, "
                "respeitando competências e iniciativa reservada.",
                (source,),
            ),
            OfficeDuty(
                "oversight",
                "Fiscalizar o Executivo estadual",
                "Participar do controle parlamentar da administração e dos recursos do estado.",
                (source,),
            ),
        ),
        (
            "Síntese das funções institucionais; não "
            "é inventário completo de competências regimentais.",
        ),
    )


MUNICIPAL_BASELINE = OfficeDutyCatalog(
    "councillor",
    "BR",
    (
        OfficeDuty(
            "legislation",
            "Deliberar sobre matérias municipais",
            "Participar da legislação de interesse local, conforme a lei orgânica do município.",
            (constitutional_source("arts. 29 e 30, I e II"),),
        ),
        OfficeDuty(
            "oversight",
            "Fiscalizar a administração municipal",
            "Participar do controle externo municipal com "
            "o auxílio do tribunal de contas competente.",
            (constitutional_source("art. 31"),),
        ),
    ),
    ("Base constitucional nacional; lei orgânica e regimento do município ainda não catalogados.",),
)

CATALOGS = {
    ("federal_deputy", "BR"): OfficeDutyCatalog(
        "federal_deputy",
        "BR",
        (
            FEDERAL_LEGISLATION,
            FEDERAL_OVERSIGHT,
            FEDERAL_BUDGET,
        ),
    ),
    ("senator", "BR"): OfficeDutyCatalog(
        "senator",
        "BR",
        (
            FEDERAL_LEGISLATION,
            FEDERAL_OVERSIGHT,
            FEDERAL_BUDGET,
            SENATE_AUTHORITIES,
        ),
    ),
    ("state_deputy", "SP"): state_catalog("SP"),
    ("state_deputy", "RJ"): state_catalog("RJ"),
    ("councillor", "BR"): MUNICIPAL_BASELINE,
}
