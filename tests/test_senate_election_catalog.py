"""Official catalog links preserve geographic identity and trusted source hosts."""

from crawlers.senado.election_catalog import parse_senate_election_catalog


def test_relative_official_article_urls_are_discovered():
    pages = parse_senate_election_catalog(
        '<a href="/noticias/infomaterias/2026/06/todas-as-eleicoes-para-o-senado-no-acre">AC</a>'
    )
    assert pages == {"AC": "https://www12.senado.leg.br/noticias/infomaterias/2026/06/"
                          "todas-as-eleicoes-para-o-senado-no-acre"}


def test_historical_district_is_not_associated_with_present_day_district():
    pages = parse_senate_election_catalog(
        '<a href="/todas-as-eleicoes-para-o-senado-na-guanabara-e-antigo-distrito-federal">'
        'Guanabara</a><a href="/todas-as-eleicoes-para-o-senado-no-distrito-federal">DF</a>'
    )
    assert len(pages) == 1
    assert pages["DF"].endswith("no-distrito-federal")


def test_external_lookalike_hosts_are_rejected():
    assert parse_senate_election_catalog(
        '<a href="https://www12.senado.leg.br.evil.test/todas-as-eleicoes-para-o-senado-no-acre">'
        'AC</a>'
    ) == {}
