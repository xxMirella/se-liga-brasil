"""Explicit official article locators, not inferred contemporary party memberships."""

# UF, name, party, observed date, publication date, kind, URL, mandatory locators.
ARTICLE_OBSERVATIONS = (
    ("SC", "Jorginho Mello", "PL", "2023-01-01", "2023-01-01", "inauguration",
     "https://www.alesc.sc.gov.br/radio/noticia/"
     "jorginho-mello-toma-posse-como-governador-de-santa-catarina/",
     ("Jorginho Mello (PL)", "empossados")),
    ("RN", "Fátima Bezerra", "PT", "2023-01-01", "2023-01-01", "inauguration",
     "https://www.al.rn.leg.br/noticia/26968/"
     "assembleia-legislativa-empossa-fatima-bezerra-e-walter-alves",
     ("empossou", "governadora reeleita Fátima Bezerra (PT)")),
    ("CE", "Elmano de Freitas", "PT", "2023-01-01", "2023-01-02", "inauguration",
     "https://www.defensoria.ce.def.br/noticia/"
     "defensoria-prestigia-posse-de-elmano-freitas-como-governador-do-ceara/",
     ("prestigiou a solenidade de posse de Elmano Freitas (PT) como governador do Ceará",)),
    ("MA", "Carlos Brandão", "PSB", "2023-02-28", "2023-02-28", "office_observation",
     "https://imperatriz.ma.gov.br/noticias/"
     "encontro-alinha-sobre-evento-popular-em-imperatriz.html",
     ("Governo do Maranhão", "governo de Carlos Brandão (PSB)")),
    ("GO", "Ronaldo Caiado", "UNIÃO", "2023-01-01", "2023-01-01", "inauguration",
     "https://portal.al.go.leg.br/noticias/129256/"
     "legislativo-empossa-o-governador-e-o-vice-governador-de-goias",
     ("empossado o governador reeleito do estado, Ronaldo Caiado (UB)",)),
    ("PI", "Rafael Fonteles", "PT", "2023-01-01", "2023-01-01", "inauguration",
     "https://www.al.pi.leg.br/comunicacao/radio/noticias-radio/"
     "rafael-fonteles-e-themistocles-filho-sao-empossados-governador-e-vice-na-assembleia-legislativa",
     ("aconteceu a posse do governador Rafael Fonteles do PT",)),
    ("PR", "Carlos Massa Ratinho Junior", "PSD", "2023-01-01", "2023-01-01", "inauguration",
     "https://www.assembleia.pr.leg.br/comunicacao/noticias/"
     "carlos-massa-ratinho-junior-e-empossado-na-assembleia-legislativa-para-o-seu-segundo",
     ("governador Carlos Massa Ratinho Junior (PSD) foi empossado",)),
    ("SE", "Fábio Mitidieri", "PSD", "2023-01-01", "2023-01-01", "inauguration",
     "https://al.se.leg.br/"
     "fabio-mitidieri-e-empossado-governador-em-solenidade-na-assembleia-legislativa/",
     ("Governador do Estado de Sergipe, Fábio Mitidieri (PSD)", "assinaram o Termo")),
    ("MT", "Mauro Mendes", "UNIÃO", "2023-01-01", "2023-01-01", "inauguration",
     "https://www.al.mt.gov.br/midia/texto/mesa-diretora-empossa-governador-e-vice-governador-"
     "de-mato-grosso/visualizar",
     ("Mauro Mendes (União Brasil)", "empossou na tarde deste domingo, 1º de janeiro de 2023")),
    ("MS", "Eduardo Riedel", None, "2023-01-01", "2023-01-01", "inauguration",
     "https://www.pc.ms.gov.br/delegado-geral-da-policia-civil-deseja-sucesso-ao-"
     "novo-governador-e-secretarios-do-mato-grosso-do-sul/",
     ("posse do governador eleito, Eduardo Riedel", "Riedel foi empossado")),
    ("AL", "Paulo Dantas", None, "2023-02-13", "2023-02-13", "office_observation",
     "https://www.al.al.leg.br/comunicacao/noticias/"
     "assembleia-abre-na-quarta-feira-os-trabalhos-do-ano-legislativo",
     ("o governador do Estado, Paulo Dantas",)),
    ("ES", "Renato Casagrande", None, "2023-04-12", "2023-04-12", "office_observation",
     "https://www.es.gov.br/Noticia/"
     "governador-recebe-nova-diretoria-de-entidade-dos-prefeitos-capixabas",
     ("O governador do Estado, Renato Casagrande, participou",)),
    ("MG", "Romeu Zema", None, "2019-01-01", "2019-01-01", "inauguration",
     "https://www.agenciaminas.mg.gov.br/noticia/"
     "romeu-zema-toma-posse-e-propoe-austeridade-uniao-e-um-pacto-por-minas",
     ("O governador Romeu Zema e o vice-governador Paulo Brant tomaram posse",)),
    ("PR", "Carlos Massa Ratinho Junior", "PSD", "2019-01-01", "2019-01-01", "inauguration",
     "https://www.assembleia.pr.leg.br/comunicacao/noticias/carlos-massa-ratinho-junior-e-"
     "empossado-como-governador-do-estado-na-assembleia-legislativa",
     ("O governador Carlos Massa Ratinho Junior (PSD) assumiu", "oficialmente empossados")),
    ("SC", "Carlos Moisés da Silva", "PSL", "2019-01-01", "2019-01-01", "inauguration",
     "https://www.alesc.sc.gov.br/radio/noticia/"
     "novo-governador-reforca-necessidade-de-gestaeo-tecnica-e-transparente/",
     ("Carlos Moisés da Silva, do PSL, foi empossado governador de Santa Catarina",)),
    ("DF", "Ibaneis Rocha", "MDB", "2019-01-01", "2019-01-01", "inauguration",
     "https://www.cl.df.gov.br/-/ibaneis-rocha-e-empossado-governador-na-cldf",
     ("Foram empossados", "governador do Distrito Federal Ibaneis Rocha (MDB)")),
    ("RR", "Antonio Denarium", "PSL", "2019-01-01", "2019-01-01", "inauguration",
     "https://al.rr.leg.br/2019/01/01/governador-empossado-sugere-uniao-entre-os-poderes-"
     "para-recuperacao-do-estado/",
     ("O governador Antonio Denarium (PSL)", "foram empossados")),
    ("AM", "Wilson Lima", None, "2019-01-02", "2019-01-02", "office_observation",
     "https://www.sefaz.am.gov.br/noticias/20368",
     ("o governador Wilson Lima ressaltou", "02 de janeiro de 2019")),
    ("AL", "Renan Filho", "MDB", "2019-01-01", "2019-01-01", "inauguration",
     "https://www.al.al.leg.br/comunicacao/noticias/renan-filho-toma-posse-para-segundo-mandato-"
     "destacando-parceria-com-o-legislativo",
     ("O governador Renan Filho (MDB) tomou posse para o seu segundo mandato",)),
    ("MS", "Reinaldo Azambuja", None, "2019-01-01", "2019-01-01", "inauguration",
     "https://agenciadenoticias.ms.gov.br/para-reinaldo-azambuja-ms-tera-retomada-do-crescimento-"
     "com-novo-ciclo-que-se-inicia-hoje/",
     ("Reeleito, o governador Reinaldo Azambuja foi empossado",)),
    ("RS", "Eduardo Leite", None, "2019-01-01", "2019-01-01", "inauguration",
     "https://estado.rs.gov.br/midia/audio/eduardo-leite-e-o-novo-governador-do-rio-grande-"
     "do-sul-201901014106",
     ("Eduardo Leite é o novo governador do Rio Grande do Sul", "após a posse outorgada")),
    ("SP", "João Doria", "PSDB", "2019-01-01", "2019-01-01", "inauguration",
     "https://al.sp.gov.br/noticia/?id=395764",
     ("João Dória, do PSDB", "tomaram posse nesta terça-feira, primeiro de janeiro")),
    ("MG", "Romeu Zema", "NOVO", "2023-02-01", "2023-02-01", "office_observation",
     "https://www.almg.gov.br/comunicacao/noticias/arquivos/"
     "Posse-de-deputados-marca-inicio-da-20-Legislatura-na-ALMG/",
     ("O governador Romeu Zema (Novo) saudou os novos parlamentares",)),
    ("MS", "Eduardo Riedel", "PSDB", "2023-02-01", "2023-02-01", "office_observation",
     "https://al.ms.gov.br/api/noticias/content/131276",
     ("presença do governador Eduardo Riedel (PSDB)",)),
    ("SE", "Belivaldo Chagas", None, "2019-01-01", "2019-01-01", "inauguration",
     "https://al.se.leg.br/meu-maior-patrimonio-e-a-credibilidade-ressalta-belivaldo-durante-posse/",
     ("empossado na tarde de hoje, dia 01 de janeiro", "governador de Sergipe, Belivaldo Chagas")),
)
