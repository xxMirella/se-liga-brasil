"""Discover actual official article URLs; historical Guanabara is not today's DF."""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

TERRITORY_PAGE_SUFFIXES = {
    "no-acre": "AC", "em-alagoas": "AL", "no-amapa": "AP", "no-amazonas": "AM",
    "na-bahia": "BA", "no-ceara": "CE", "no-distrito-federal": "DF",
    "no-espirito-santo": "ES", "em-goias": "GO", "no-maranhao": "MA",
    "em-mato-grosso": "MT", "no-mato-grosso-do-sul": "MS", "em-minas-gerais": "MG",
    "no-para": "PA", "na-paraiba": "PB", "no-parana": "PR", "em-pernambuco": "PE",
    "no-piaui": "PI", "no-rio-de-janeiro": "RJ", "no-rio-grande-do-norte": "RN",
    "no-rio-grande-do-sul": "RS", "em-rondonia": "RO", "em-roraima": "RR",
    "em-santa-catarina": "SC", "em-sao-paulo": "SP", "em-sergipe": "SE",
    "no-tocantins": "TO",
}
ARTICLE_PREFIX = "todas-as-eleicoes-para-o-senado-"


class SenateElectionCatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pages = {}

    def handle_starttag(self, tag, attributes):
        if tag != "a":
            return
        url = urljoin("https://www12.senado.leg.br", dict(attributes).get("href", ""))
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "www12.senado.leg.br":
            return
        slug = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        if not slug.startswith(ARTICLE_PREFIX):
            return
        territory = TERRITORY_PAGE_SUFFIXES.get(slug.removeprefix(ARTICLE_PREFIX))
        if territory:
            self.pages[territory] = url


def parse_senate_election_catalog(html):
    parser = SenateElectionCatalogParser()
    parser.feed(html)
    return parser.pages
