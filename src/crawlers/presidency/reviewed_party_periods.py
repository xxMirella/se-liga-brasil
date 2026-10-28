"""Source-reviewed party periods, kept separate from presidential exercise dates."""

REVIEWED_PRESIDENTIAL_PARTY_PERIODS = (
    {
        "person_id": "arquivo-nacional-president:179",
        "exercise_starts_on": "1930-11-03",
        "starts_on": "1931-01-01",
        "ends_before": "1937-01-01",
        "date_precision": "year",
        "political_party": "Sem partido",
        "political_party_code": "historical:BR:no_affiliation",
        "political_party_status": "verified_government_classification",
        "political_party_context": "original_research_annual_government_classification",
        "political_party_limitation": (
            "academic_government_classification_not_personal_affiliation_event_dates"
        ),
        "source_url": 'https://files.ufgd.edu.br/arquivos/arquivos/78/MESTRADO-DOUTORADO-EDUCACAO/Teses%20Defendidas/Tese%20Carlos%20Eduardo%20Pronta%20para%20publica%C3%A7%C3%A3o.pdf',
        "locator": "Brasil como presidente sem partido (1930-1945)",
        "supporting_sources": [{
            "url": 'https://periodicos.fclar.unesp.br/estudos/article/download/13979/9355/42921',
            "locators": [
                "ininterruptos (1930-1945), durante o qual Getúlio Vargas governou sem partido",
            ],
        }],
    },
    {
        "person_id": "arquivo-nacional-president:196",
        "exercise_starts_on": "1964-04-15",
        "starts_on": "1965-10-27",
        "ends_before": "1965-11-22",
        "political_party": "Partidos extintos",
        "political_party_code": "historical:BR:party_extinction:1965",
        "political_party_status": "verified_official_government_party_classification",
        "political_party_context": "legal_party_extinction_not_personal_affiliation",
        "political_party_limitation": (
            "documented_window_before_ac4_organizations_not_presidential_affiliation"
        ),
        "source_url": 'https://www2.camara.leg.br/legin/fed/atoins/1960-1969/atoinstitucional-2-27-outubro-1965-363603-publicacaooriginal-1-pe.html',
        "locator": (
            "Ficam extintos os atuais partidos políticos e cancelados os respectivos registros."
        ),
        "supporting_sources": [{
            "url": 'https://www2.camara.leg.br/legin/fed/atocom/1960-1969/atocomplementar-4-20-novembro-1965-351199-publicacaooriginal-1-pe.html',
            "locators": [
                "atribuições de partidos políticos enquanto êstes não se constituírem.",
                "Art. 22. Êste Ato entrará em vigor na data de sua publicação.",
                "22/11/1965, Página 11857 (Publicação Original)",
            ],
        }],
    },
    {
        'person_id': 'arquivo-nacional-president:216',
        'exercise_starts_on': '1894-11-15',
        'starts_on': '1894-11-15',
        'ends_before': '1898-11-15',
        'political_party': 'PRP',
        'political_party_code': 'historical:SP:PRP:1873',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/216-prudente-jose-de-morais-barros',
        'locator': (
            'Prudente de Morais foi o primeiro presidente eleito diretamente pelo PRP'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:209',
        'exercise_starts_on': '1910-11-15',
        'starts_on': '1910-11-15',
        'ends_before': '1914-11-15',
        'political_party': 'PRC',
        'political_party_code': 'historical:BR:PRC:1910',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/209-hermes-rodrigues-da-fonseca',
        'locator': 'Em 1910, foi um dos fundadores do Partido Republicano Conservador.',
    },
    {
        'person_id': 'arquivo-nacional-president:181',
        'exercise_starts_on': '1946-01-31',
        'starts_on': '1946-01-31',
        'ends_before': '1951-01-31',
        'political_party': 'PSD',
        'political_party_code': 'historical:BR:PSD:1945',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/181-eurico-gaspar-dutra',
        'locator': (
            'Candidatou-se à presidência da República pelo Partido Social Democrático '
            '(PSD)'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:179',
        'exercise_starts_on': '1951-01-31',
        'starts_on': '1951-01-31',
        'ends_before': '1954-08-24',
        'political_party': 'PTB',
        'political_party_code': 'historical:BR:PTB:1945',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/179-getulio-dorneles-vargas',
        'locator': (
            'Em 1950, concorreu novamente à presidência da República, pelo Partido '
            'Trabalhista Brasileiro'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:189',
        'exercise_starts_on': '1967-03-15',
        'starts_on': '1967-03-15',
        'ends_before': '1969-08-31',
        'political_party': 'ARENA',
        'political_party_code': 'historical-presidency:BR:ARENA',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/189-artur-da-costa-e-silva',
        'locator': (
            'desincompatibilizou-se do cargo para candidatar-se às eleições indiretas na '
            'legenda da Arena.'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:185',
        'exercise_starts_on': '1961-01-31',
        'starts_on': '1961-01-31',
        'ends_before': '1961-08-25',
        'political_party': 'PTN',
        'political_party_code': 'historical:BR:PTN:1945',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www12.senado.leg.br/noticias/especiais/arquivo-s/ha-60-anos-congresso-aceitou-renuncia-e-abortou-golpe-de-janio-quadros',
        'locator': 'Jânio pertencia ao PTN',
    },
    {
        'person_id': 'arquivo-nacional-president:188',
        'exercise_starts_on': '1954-08-24',
        'starts_on': '1954-08-24',
        'ends_before': '1955-11-08',
        'political_party': 'PSP',
        'political_party_code': 'historical:BR:PSP:1946',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www2.camara.leg.br/atividade-legislativa/plenario/discursos/escrevendohistoria/visitantes/panorama-das-decadas/decada-de-50',
        'locator': (
            'O vice-presidente Café Filho assume o poder nesse mesmo dia e, por não ter '
            'o PSP, seu partido'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:195',
        'exercise_starts_on': '1955-11-08',
        'starts_on': '1955-11-08',
        'ends_before': '1955-11-11',
        'political_party': 'PSD',
        'political_party_code': 'historical:BR:PSD:1945',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www.camara.leg.br/deputados/130731/biografia',
        'locator': 'Presidente da República, Partido: PSD, Período: 1955 a 1955.',
    },
    {
        'person_id': 'arquivo-nacional-president:194',
        'exercise_starts_on': '1955-11-11',
        'starts_on': '1955-11-11',
        'ends_before': '1956-01-31',
        'political_party': 'PSD',
        'political_party_code': 'historical:BR:PSD:1945',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www12.senado.leg.br/noticias/materias/2016/05/02/ha-190-anos-senado-ajuda-a-debelar-as-grandes-crises-do-brasil',
        'locator': 'Quem assume o governo é Nereu Ramos (PSD-\u200bSC)',
    },
    {
        'person_id': 'arquivo-nacional-president:183',
        'exercise_starts_on': '1974-03-15',
        'starts_on': '1974-03-15',
        'ends_before': '1979-03-15',
        'political_party': 'ARENA',
        'political_party_code': 'historical-presidency:BR:ARENA',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://memoriapolitica.alesc.sc.gov.br/legislativo/deputado-estadual/legislaturas/118-8a_Legislatura',
        'locator': (
            '15/03/1974 a 15/03/1979 - General Ernesto Geisel, da ARENA, Presidente da '
            'República'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:205',
        'exercise_starts_on': '2011-01-01',
        'starts_on': '2011-01-01',
        'ends_before': '2016-05-12',
        'political_party': 'PT',
        'political_party_code': 'historical-presidency:BR:PT',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www12.senado.leg.br/noticias/materias/2016/08/29/dilma-rousseff-a-primeira-mulher-a-presidir-o-brasil',
        'locator': 'Em 2010, Dilma elegeu-se pelo PT para a Presidência do país',
    },
    {
        'person_id': 'arquivo-nacional-president:203',
        'exercise_starts_on': '1992-10-02',
        'starts_on': '1992-10-02',
        'ends_before': '1995-01-01',
        'political_party': 'Sem partido',
        'political_party_code': 'historical-presidency:BR:Sem partido',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www12.senado.leg.br/noticias/materias/2011/07/04/ana-amelia-itamar-tinha-ousadia-coragem-simplicidade-e-honestidade',
        'locator': (
            'Itamar demonstrou isenção e independência quando, sem partido, formou um '
            'governo de coalizão'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:201',
        'exercise_starts_on': '2016-05-12',
        'starts_on': '2016-05-12',
        'ends_before': '2016-08-31',
        'political_party': 'PMDB',
        'political_party_code': 'historical-presidency:BR:PMDB',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www.camara.leg.br/deputados/73552/biografia',
        'locator': 'Presidente da República, Partido: MDB, Período: 2016 a 2018.',
    },
    {
        'person_id': 'arquivo-nacional-president:201',
        'exercise_starts_on': '2016-08-31',
        'starts_on': '2016-08-31',
        'ends_before': '2018-05-15',
        'political_party': 'PMDB',
        'political_party_code': 'historical-presidency:BR:PMDB',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www.camara.leg.br/deputados/73552/biografia',
        'locator': 'Presidente da República, Partido: MDB, Período: 2016 a 2018.',
    },
    {
        'person_id': 'arquivo-nacional-president:201',
        'exercise_starts_on': '2016-08-31',
        'starts_on': '2018-05-15',
        'ends_before': '2019-01-01',
        'political_party': 'MDB',
        'political_party_code': 'historical-presidency:BR:MDB',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_historical_government_party_classification',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www.camara.leg.br/deputados/73552/biografia',
        'locator': 'Presidente da República, Partido: MDB, Período: 2016 a 2018.',
    },
    {
        'person_id': 'arquivo-nacional-president:199',
        'exercise_starts_on': '2019-01-01',
        'starts_on': '2019-01-01',
        'ends_before': '2019-11-01',
        'political_party': 'PSL',
        'political_party_code': 'historical-presidency:BR:PSL',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_dated_affiliation_transition',
        'political_party_limitation': 'november_2019_departure_day_unresolved_gap_preserved',
        'source_url': 'https://agenciabrasil.ebc.com.br/politica/noticia/2021-11/presidente-bolsonaro-assina-filiacao-ao-pl',
        'locator': (
            'Eleito em 2018 pelo PSL, Bolsonaro deixou o partido em novembro de 2019 e '
            'não estava filiado a nenhum partido.'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:199',
        'exercise_starts_on': '2019-01-01',
        'starts_on': '2019-12-01',
        'ends_before': '2021-11-30',
        'political_party': 'Sem partido',
        'political_party_code': 'historical-presidency:BR:Sem partido',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_dated_affiliation_transition',
        'political_party_limitation': 'november_2019_departure_day_unresolved_gap_preserved',
        'source_url': 'https://agenciabrasil.ebc.com.br/politica/noticia/2021-11/presidente-bolsonaro-assina-filiacao-ao-pl',
        'locator': (
            'Eleito em 2018 pelo PSL, Bolsonaro deixou o partido em novembro de 2019 e '
            'não estava filiado a nenhum partido.'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:199',
        'exercise_starts_on': '2019-01-01',
        'starts_on': '2021-11-30',
        'ends_before': '2023-01-01',
        'political_party': 'PL',
        'political_party_code': 'historical-presidency:BR:PL',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'official_dated_affiliation_transition',
        'political_party_limitation': 'november_2019_departure_day_unresolved_gap_preserved',
        'source_url': 'https://agenciabrasil.ebc.com.br/politica/noticia/2021-11/presidente-bolsonaro-assina-filiacao-ao-pl',
        'locator': (
            'Eleito em 2018 pelo PSL, Bolsonaro deixou o partido em novembro de 2019 e '
            'não estava filiado a nenhum partido.'
        ),
    },
    {
        'person_id': 'arquivo-nacional-president:179',
        'exercise_starts_on': '1930-11-03',
        'starts_on': '1937-12-02',
        'ends_before': '1945-05-28',
        'political_party': 'Partidos proibidos',
        'political_party_code': 'historical-presidency:BR:Partidos proibidos',
        'political_party_status': 'verified_official_government_party_classification',
        'political_party_context': 'legal_party_prohibition_not_personal_affiliation',
        'political_party_limitation': (
            'official_historical_attribution_not_continuous_affiliation_certificate'
        ),
        'source_url': 'https://www2.camara.leg.br/legin/fed/declei/1930-1939/decreto-lei-37-2-dezembro-1937-354175-publicacaooriginal-1-pe.html',
        'locator': 'Ficam dissolvidos, nesta data, todos os partidos políticos.',
        'supporting_sources': [{
            'url': 'https://www2.camara.leg.br/legin/fed/declei/1940-1949/decreto-lei-7586-28-maio-1945-417387-publicacaooriginal-1-pe.html',
            'locators': [
                'Art. 142. Fica revogado o Decreto-lei nº 37, de 2 de dezembro de 1937',
                'Art. 145. Esta lei entrará em vigor na data de sua publicação.',
                '28/5/1945, Página 9436 (Publicação Original)',
            ],
        }],
    },
    {
        'person_id': 'arquivo-nacional-president:214',
        'exercise_starts_on': '1898-11-15',
        'starts_on': '1898-11-15',
        'ends_before': '1902-11-15',
        'political_party': 'PRP',
        'political_party_code': 'historical:SP:PRP:1873',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-paulista-prp',
        'locator': 'Manuel Ferraz de Campos Sales Presidente (a) da República 1898 1902',
    },
    {
        'person_id': 'arquivo-nacional-president:215',
        'exercise_starts_on': '1902-11-15',
        'starts_on': '1902-11-15',
        'ends_before': '1906-11-15',
        'political_party': 'PRP',
        'political_party_code': 'historical:SP:PRP:1873',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-paulista-prp',
        'locator': 'Francisco de Paula Rodrigues Alves Presidente (a) 1902 1906',
    },
    {
        'person_id': 'arquivo-nacional-president:178',
        'exercise_starts_on': '1906-11-15',
        'starts_on': '1906-11-15',
        'ends_before': '1909-06-14',
        'political_party': 'PRM',
        'political_party_code': 'historical:MG:PRM:1888',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-mineiro-prm',
        'locator': 'Afonso Augusto Moreira Pena Presidente (a) 1906 1909',
    },
    {
        'person_id': 'arquivo-nacional-president:211',
        'exercise_starts_on': '1914-11-15',
        'starts_on': '1914-11-15',
        'ends_before': '1918-11-15',
        'political_party': 'PRM',
        'political_party_code': 'historical:MG:PRM:1888',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-mineiro-prm',
        'locator': 'Venceslau Brás Pereira Gomes Presidente (a) 1914 1918',
    },
    {
        'person_id': 'arquivo-nacional-president:186',
        'exercise_starts_on': '1919-07-28',
        'starts_on': '1919-07-28',
        'ends_before': '1922-11-15',
        'political_party': 'PRM',
        'political_party_code': 'historical:MG:PRM:1888',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-mineiro-prm',
        'locator': 'Epitácio Lindolfo da Silva Pessoa Presidente (a) da República 1919 1922',
    },
    {
        'person_id': 'arquivo-nacional-president:207',
        'exercise_starts_on': '1922-11-15',
        'starts_on': '1922-11-15',
        'ends_before': '1926-11-15',
        'political_party': 'PRM',
        'political_party_code': 'historical:MG:PRM:1888',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-mineiro-prm',
        'locator': 'Artur da Silva Bernardes Presidente (a) da República 1922 1926',
    },
    {
        'person_id': 'arquivo-nacional-president:208',
        'exercise_starts_on': '1926-11-15',
        'starts_on': '1926-11-15',
        'ends_before': '1930-10-24',
        'political_party': 'PRP',
        'political_party_code': 'historical:SP:PRP:1873',
        'political_party_status': 'verified_government_classification',
        'political_party_context': 'original_research_government_classification',
        'political_party_limitation': (
            'classification_of_government_not_affiliation_certificate'
        ),
        'source_url': 'https://neamp.pucsp.br/organizacoes/partido-republicano-paulista-prp',
        'locator': 'Washington Luís Pereira de Souza Presidente (a) 1926 1930',
    },
    {
        "person_id": "arquivo-nacional-president:212",
        "exercise_starts_on": "1889-11-15",
        "starts_on": "1889-11-15",
        "ends_before": "1891-11-23",
        "political_party": "Sem partido",
        "political_party_code": "historical:BR:no_affiliation",
        "political_party_status": "verified_government_classification",
        "political_party_context": "original_research_government_classification",
        "political_party_limitation": "classification_of_government_not_affiliation_certificate",
        "source_url": (
            "https://repositorio.unb.br/bitstream/10482/42688/3/2021_RodrigoLentz.pdf"
        ),
        "locator": (
            "a 1894, com os marechais Deodoro da Fonseca e Floriano Peixoto, ambos sem partido"
        ),
    },
    {
        "person_id": "arquivo-nacional-president:213",
        "exercise_starts_on": "1891-11-23",
        "starts_on": "1891-11-23",
        "ends_before": "1894-11-15",
        "political_party": "Sem partido",
        "political_party_code": "historical:BR:no_affiliation",
        "political_party_status": "verified_government_classification",
        "political_party_context": "original_research_government_classification",
        "political_party_limitation": "classification_of_government_not_affiliation_certificate",
        "source_url": (
            "https://repositorio.unb.br/bitstream/10482/42688/3/2021_RodrigoLentz.pdf"
        ),
        "locator": (
            "a 1894, com os marechais Deodoro da Fonseca e Floriano Peixoto, ambos sem partido"
        ),
    },
    {
        "person_id": "arquivo-nacional-president:206",
        "exercise_starts_on": "1918-11-15",
        "starts_on": "1918-11-15",
        "ends_before": "1919-07-28",
        "political_party": "PRM",
        "political_party_code": "historical:MG:PRM:1888",
        "political_party_status": "verified_government_classification",
        "political_party_context": "original_research_government_classification",
        "political_party_limitation": "classification_of_government_not_affiliation_certificate",
        "source_url": 'https://bndigital.bn.gov.br/artigos/acervo-da-bn-a-gazeta-vida-e-morte-de-um-vespertino-paulistano/',
        "locator": "Epitácio Pessoa, do mesmo PRM de Moreira",
    },
    {
        "person_id": "arquivo-nacional-president:190",
        "exercise_starts_on": "1969-10-30",
        "starts_on": "1969-10-30",
        "ends_before": "1974-03-15",
        "political_party": "ARENA",
        "political_party_code": "historical:BR:ARENA:1966",
        "political_party_status": "verified_government_classification",
        "political_party_context": "original_research_government_classification",
        "political_party_limitation": "classification_of_government_not_affiliation_certificate",
        "source_url": "https://neamp.pucsp.br/liderancas/emilio-garrastazu-medici",
        "locator": (
            "Aliança Renovadora Nacional (ARENA) Presidente (a) da República 1969 1974"
        ),
    },
    {
        "person_id": "arquivo-nacional-president:193",
        "exercise_starts_on": "1979-03-15",
        "starts_on": "1979-03-15",
        "ends_before": "1980-01-01",
        "date_precision": "year",
        "political_party": "ARENA",
        "political_party_code": "historical:BR:ARENA:1966",
        "political_party_status": "verified_official_government_party_classification",
        "political_party_context": "official_annual_government_party_classification",
        "political_party_limitation": (
            "annual_classification_boundaries_not_personal_affiliation_event_dates"
        ),
        "source_url": 'https://www.camara.leg.br/noticias/93692-os-presidetes-da-ditadura-militar/',
        "locator": (
            'Figueiredo foi eleito pela Arena, por escolha indireta no Colégio Eleitoral, em 1978.'
        ),
    },
    {
        "person_id": "arquivo-nacional-president:193",
        "exercise_starts_on": "1979-03-15",
        "starts_on": "1980-01-01",
        "ends_before": "1985-03-15",
        "date_precision": "year",
        "political_party": "PDS",
        "political_party_code": "historical:BR:PDS:1980",
        "political_party_status": "verified_official_government_party_classification",
        "political_party_context": "official_annual_government_party_classification",
        "political_party_limitation": (
            "annual_classification_boundaries_not_personal_affiliation_event_dates"
        ),
        "source_url": 'https://www2.camara.leg.br/atividade-legislativa/plenario/discursos/escrevendohistoria/visitantes/panorama-das-decadas/copy_of_decada-de-80',
        "locator": 'Em 1980, surgem o Partido Democrático Social (PDS), novo partido governista',
    },
)
