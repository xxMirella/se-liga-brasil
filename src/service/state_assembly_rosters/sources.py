"""Official institutional entry points; acquired content must pass its source-specific parser."""

from crawlers.alap.roster import parse_current_roster as parse_alap
from crawlers.alba.roster import parse_current_roster as parse_alba
from crawlers.aleal.roster import parse_current_roster as parse_aleal
from crawlers.alece.roster import parse_current_roster as parse_alece
from crawlers.alema.roster import parse_current_roster as parse_alema
from crawlers.alems.roster import parse_current_roster as parse_alems
from crawlers.alep.roster import parse_current_roster as parse_alep
from crawlers.alepa.roster import parse_current_roster as parse_alepa
from crawlers.alepe.roster import parse_current_roster as parse_alepe
from crawlers.alerj.roster import parse_current_roster as parse_alerj
from crawlers.ales.roster import parse_current_roster as parse_ales
from crawlers.alesc.roster import parse_current_roster as parse_alesc
from crawlers.alese.roster import parse_current_roster as parse_alese
from crawlers.alesp.roster import parse_current_roster as parse_alesp
from crawlers.aleto.roster import parse_current_roster as parse_aleto
from crawlers.almg.roster import parse_current_roster as parse_almg
from crawlers.almt.roster import parse_current_roster as parse_almt
from crawlers.alrn.roster import parse_current_roster as parse_alrn
from crawlers.alrs.roster import parse_current_roster as parse_alrs
from crawlers.cldf.roster import parse_current_roster as parse_cldf
from crawlers.interlegis.roster import parse_current_roster as parse_sapl

SOURCE_URLS = {
    "AL": ("aleal", "https://www.al.al.leg.br/processo-legislativo/20-a-legislatura", ".html"),
    "AP": (
        "alap",
        "https://www.al.ap.leg.br/pagina.php?pg=exibir_parlamentar&iddeputado=78",
        ".html",
    ),
    "BA": ("alba", "https://albalegis.nopapercloud.com.br/spl/parlamentares.aspx", ".html"),
    "ES": ("ales", "https://www.al.es.gov.br/Deputados", ".html"),
    "MA": ("alema", "https://www.al.ma.leg.br/sitealema/deputados/", ".html"),
    "MT": ("almt", "https://www.al.mt.gov.br/parlamento/deputados", ".html"),
    "MS": ("alems", "https://al.ms.gov.br/Partidos/Lista", ".html"),
    "PA": ("alepa", "https://www.alepa.pa.gov.br/Home/Page/Deputados", ".html"),
    "PB": ("alpb", "https://sapl3.al.pb.leg.br/parlamentar?iframe=1&incluir;=0&", ".html"),
    "PE": ("alepe", "https://www.alepe.pe.gov.br/parlamentares/", ".html"),
    "PI": ("alepi", "https://sapl.al.pi.leg.br/parlamentar/", ".html"),
    "RN": (
        "alrn",
        "https://api-transparencialegislativa.al.rn.leg.br/"
        "elegis-api-transp-legislativa/parlamentar",
        ".json",
    ),
    "RS": (
        "alrs",
        "https://transparencia.al.rs.gov.br/parlamentares/presencas-plenario/pesquisa?ano=2026&mes=10",
        ".html",
    ),
    "RO": ("alero", "https://www.al.ro.leg.br/deputados/perfil/", ".html"),
    "RR": ("alrr", "https://al.rr.leg.br/deputados-estaduais-2023/", ".html"),
    "SE": ("alese", "https://aleselegis.al.se.leg.br/spl/parlamentares.aspx", ".html"),
    "TO": ("aleto", "https://www.al.to.leg.br/perfil", ".html"),
    "PR": ("alep", "https://www.assembleia.pr.leg.br/deputados/conheca", ".html"),
    "SC": ("alesc", "https://www.alesc.sc.gov.br/deputados/", ".html"),
    "GO": ("alego", "https://portal.al.go.leg.br/deputados/em-exercicio", ".html"),
    "CE": ("alece", "https://www.al.ce.gov.br/deputados", ".html"),
    "AC": ("aleac", "https://sapl.al.ac.leg.br/api/parlamentares/parlamentar/?ativo=true", ".json"),
    "AM": ("aleam", "https://sapl.al.am.leg.br/api/parlamentares/parlamentar/?ativo=true", ".json"),
    "SP": ("alesp", "https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml", ".xml"),
    "RJ": ("alerj", "https://www.alerj.rj.gov.br/Deputados/QuemSao", ".html"),
    "DF": ("cldf", "https://www.cl.df.gov.br/", ".html"),
    "MG": (
        "almg",
        "https://dadosabertos.almg.gov.br/api/v2/deputados/em_exercicio?formato=json",
        ".json",
    ),
}

PARSERS = {
    "RS": parse_alrs,
    "AL": parse_aleal,
    "RN": parse_alrn,
    "AP": parse_alap,
    "AC": parse_sapl,
    "AM": parse_sapl,
    "CE": parse_alece,
    "BA": parse_alba,
    "SE": parse_alese,
    "MS": parse_alems,
    "TO": parse_aleto,
    "MT": parse_almt,
    "PA": parse_alepa,
    "PB": parse_sapl,
    "PI": parse_sapl,
    "ES": parse_ales,
    "PE": parse_alepe,
    "MA": parse_alema,
    "SP": parse_alesp,
    "RJ": parse_alerj,
    "MG": parse_almg,
    "DF": parse_cldf,
    "PR": parse_alep,
    "SC": parse_alesc,
}
