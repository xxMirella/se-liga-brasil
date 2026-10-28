"""Reviewed historical claims: electoral support and foundation never imply term affiliation."""

from crawlers.presidency.acquisition import GALLERY_URL

REVIEWED_BIOGRAPHIES = (
    {
        "record_id": "camara-chronology:cf83c3d11f1be0bee48f186a",
        "archive_article_id": "207",
        "url": GALLERY_URL + "/Bernardes/biografia-completa",
        "subject": "Artur Bernardes", "kind": "party_leadership",
        "locator": "Líder do PRM (1918-1932)",
        "political_party_code": "historical:BR-MG:PRM",
        "political_party": "Partido Republicano Mineiro",
        "political_party_abbreviation": "PRM", "year_start": 1918, "year_end": 1932,
    },
    {
        "record_id": "camara-chronology:4802a632774917f8fa7f7ce8",
        "archive_article_id": "216",
        "url": "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-"
               "presidenciais/assuntos/biografias/216-prudente-jose-de-morais-barros",
        "subject": "Prudente José de Morais Barros", "kind": "presidential_election",
        "locator": "Prudente de Morais foi o primeiro presidente eleito diretamente pelo PRP, "
                   "com apoio do PRF (Partido Republicano Federal)",
        "political_party_code": "historical:BR-SP:PRP",
        "political_party": "Partido Republicano Paulista",
        "political_party_abbreviation": "PRP", "year_start": 1894, "year_end": 1894,
        "supporting_political_party_code": "historical:BR:PRF:1893",
        "display_name": "Prudente de Morais",
    },
    {
        "record_id": "camara-chronology:e3f7acf4314133343120b618",
        "archive_article_id": "214",
        "url": "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-"
               "presidenciais/assuntos/biografias/214-manuel-ferraz-de-campos-sales",
        "subject": "Manuel Ferraz de Campos Sales", "kind": "party_foundation",
        "locator": "participou, no ano seguinte, da fundação do Partido Republicano Paulista "
                   "(PRP)",
        "political_party_code": "historical:BR-SP:PRP",
        "political_party": "Partido Republicano Paulista",
        "political_party_abbreviation": "PRP", "year_start": 1873, "year_end": 1873,
    },
    {
        "record_id": "camara-chronology:df98655322bef191f5672f90",
        "archive_article_id": "209",
        "url": GALLERY_URL + "/hermesfonseca/biografia-completa",
        "subject": "Hermes Rodrigues da Fonseca", "kind": "party_foundation",
        "locator": "Em 1910, foi um dos fundadores do Partido Republicano Conservador",
        "political_party_code": "historical:BR:PRC:1910",
        "political_party": "Partido Republicano Conservador",
        "political_party_abbreviation": "PRC", "year_start": 1910, "year_end": 1910,
    },
    {
        "record_id": "arquivo-nacional-president:191", "archive_article_id": "191",
        "url": "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-"
               "presidenciais/assuntos/biografias/191-joao-belchior-marques-goulart",
        "subject": "João Belchior Marques Goulart", "kind": "party_leadership",
        "locator": "presidente nacional do PTB (1952–1964)",
        "political_party_code": "historical:BR:PTB:1945",
        "political_party": "Partido Trabalhista Brasileiro",
        "political_party_abbreviation": "PTB", "year_start": 1952, "year_end": 1964,
    },
    {
        "record_id": "arquivo-nacional-president:184", "archive_article_id": "184",
        "url": "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-"
               "presidenciais/assuntos/biografias/184-pascoal-ranieri-mazzilli",
        "subject": "Pascoal Ranieri Mazzilli", "kind": "dated_office_political_party",
        "locator": "Eleito deputado federal pelo Partido Social Democrático (PSD) de São Paulo "
                   "(1951-1966)",
        "political_party_code": "historical:BR:PSD:1945",
        "political_party": "Partido Social Democrático",
        "political_party_abbreviation": "PSD", "year_start": 1951, "year_end": 1966,
    },
)
