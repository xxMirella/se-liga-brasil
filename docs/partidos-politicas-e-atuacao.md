# Partidos: políticas, projetos e atuação (comportamento antes do discurso)

Gerado em 28/10/2026 pelo agente de políticas e projetos. Alimenta a rubrica proposta em `data/political-orientation/party-model/rubric.json` (canais `implemented_policy` e `initiative_agenda`). **Não classifica ninguém**: reúne evidência datada, com fonte e nível de prova. Votações nominais e estatutos são tratados por outros agentes.

## Como ler

Cada afirmação aqui tem um de três tipos, e os JSON repetem o campo `tipo_de_afirmacao`:

- **Fato**: dado oficial ou documento primário (lei existe e foi sancionada em tal data; deputado X, partido Y, apresentou o projeto Z; candidato do partido W foi eleito).
- **Interpretação acadêmica**: classificação ou análise publicada por pesquisadores (survey de especialistas, CPDOC/FGV, classificações de governo já presentes em `executive_orientation_evidence.json`).
- **Opinião/codificação do agente**: a direção (-1/0/+1) dada a uma lei no indicador da rubrica e as leituras comparativas deste texto. Está marcada como proposta a revisar.

Níveis de prova: **A** dado oficial agregado localmente ou documento primário verificado nesta sessão; **B** fonte secundária arquivada localmente (CPDOC/FGV); **C** conhecimento de literatura não verificado (não usado como base de nenhum número); **D** indisponível ou não verificado.

Princípio principal: **tema mede foco, não direção**. Um projeto de "Trabalho e Emprego" pode ampliar ou reduzir direitos. A razão de foco (parcela do tema nas proposições do partido dividida pela parcela de todos os partidos no mesmo período) mostra o que o partido prioriza. A direção vem de lei implementada, voto ou texto.

## O que foi coletado (arquivos em `data/political-orientation/party-model/policies/`)

| Item | Cobertura | Onde |
|---|---|---|
| Proposições de autoria, Câmara | arquivos anuais 1980-2026 (proposições, autores com partido, temas oficiais). 188 arquivos, 1,4 GB originais, sha256 em `manifest.json` | `raw/camara`, `derived/camara_party_theme_counts_1980_2026.csv` |
| Matérias de autoria, Senado | 1980-2026, primeiro autor com partido/UF, sem tema | `raw/senado`, `derived/senado_party_type_counts_1980_2026.csv` |
| Eleitos (TSE consulta_cand) | 1994-2024: presidente, governadores, prefeitos (total e capitais), vagas | `raw/tse`, `derived/tse_elected_offices.json` |
| Apoio presidencial 1º turno | 1994-2022, via coligação registrada | `derived/presidential_coalition_support.json` |
| Plataformas presidenciais (TSE) | 2018 e 2022 analisadas; 2010 e 2014 arquivadas sem análise | `raw/tse_platforms`, `derived/presidential_platform_theme_focus.json` |
| Atos legais | 33 leis, emendas e decretos, todos verificados no LexML (título e sha256) | `curated/legal_acts.json`, `raw/lexml`, `derived/legal_acts_verified.json` |
| Fontes secundárias | CPDOC/FGV (já arquivadas no projeto), 12 itens | `curated/qualitative_items.json` |
| Evidência por partido | 23 arquivos | `parties/<ID>/party_policy_evidence.json` |

Reprodução: `scripts/collect_party_policy_projects.py`, `aggregate_party_elected_offices.py`, `aggregate_presidential_coalitions.py`, `analyze_presidential_platform_focus.py`, `verify_policy_legal_acts.py`, `build_party_policy_evidence.py`.

Verificação de rótulo partidário nos dados da Câmara: o partido registrado é o da época (DEM só aparece a partir de 2007, UNIÃO a partir de 2022, PFL até 2007, PL sem registros entre 2007 e 2018), com raras anomalias de 1 a 2 proposições. Isso sustenta usar "partido do autor na apresentação", mas é verificação por amostra de rótulos, não auditoria proposição a proposição.

Agrupamentos de siglas (`PFL_DEM_UNIAO`, `PP_PPR_PPB`, `PL_PR`, `MDB`, `CIDADANIA_PPS`, etc.) são de **leitura**, declarados no script; o detalhe por sigla fica em `por_sigla` e nada é transferido entre siglas sem indicação. UNIÃO inclui só o que a Câmara rotulou assim (o PSL fica separado).

## Mapeamento tema oficial para rubrica

A taxonomia é a oficial da Câmara (34 temas). O mapeamento para indicadores está em `THEME_TO_INDICATORS` no script `build_party_policy_evidence.py` (por exemplo: Trabalho e Emprego para E4; Previdência e Assistência para E2/E5; Estrutura Fundiária para E8; Direito Penal para C4; Defesa e Segurança para C4/C5; Direitos Humanos e Minorias para C1; Meio Ambiente para C7). Temas sem relação clara (Homenagens, Processo Legislativo, Turismo, Esporte) ficam sem indicador. O Senado não tem tema oficial na listagem: só contagem por tipo.

## Foco temático 2011-2026 (razão de foco; 1,00 é a média de todos os partidos)

Proposições normativas (PL, PLP, PEC) com ao menos um deputado do partido entre os autores. Partidos com menos de 300 proposições no período foram omitidos. Valores acima de 1,3 ou abaixo de 0,7 são os que merecem atenção.

| Partido | n | Trabalho | Previd./Assist. | Dir. humanos | Penal | Defesa/Seg. | Terra | Meio amb. | Educação | Cultura |
|---|---|---|---|---|---|---|---|---|---|---|
| PT | 5840 | 1,28 | 1,30 | 1,14 | 0,62 | 0,69 | 1,44 | 0,97 | 1,17 | 1,16 |
| PSB | 3775 | 1,12 | 1,16 | 0,96 | 0,80 | 0,57 | 0,42 | 0,81 | 0,98 | 0,99 |
| PDT | 3807 | 1,16 | 1,23 | 1,01 | 0,75 | 0,82 | 0,42 | 1,18 | 1,21 | 1,01 |
| PCdoB | 1099 | 1,77 | 1,31 | 1,03 | 0,80 | 0,71 | 0,44 | 0,43 | 1,35 | 1,52 |
| PSOL | 1129 | 1,32 | 1,49 | 1,87 | 0,96 | 1,29 | 0,65 | 1,36 | 1,52 | 1,96 |
| PSDB | 4049 | 0,80 | 0,97 | 0,91 | 0,81 | 0,64 | 0,42 | 0,74 | 0,94 | 0,77 |
| MDB | 5894 | 0,96 | 0,84 | 0,83 | 0,76 | 0,73 | 1,43 | 0,91 | 0,91 | 0,95 |
| PFL/DEM/UNIÃO | 5263 | 0,84 | 0,86 | 0,99 | 1,29 | 1,26 | 0,81 | 1,08 | 1,02 | 0,99 |
| PP/PPR/PPB | 4537 | 0,92 | 1,04 | 0,89 | 0,98 | 0,96 | 1,43 | 1,13 | 0,94 | 0,98 |
| PL/PR | 6590 | 0,90 | 0,84 | 0,95 | 1,66 | 1,95 | 2,22 | 0,72 | 0,84 | 1,20 |
| PSL | 2088 | 0,89 | 0,74 | 0,75 | 1,79 | 1,51 | 0,94 | 0,61 | 0,89 | 0,74 |
| Republicanos | 4304 | 1,07 | 0,96 | 1,33 | 1,11 | 1,08 | 1,05 | 1,06 | 1,02 | 1,12 |
| PSD | 4488 | 0,84 | 0,83 | 0,87 | 0,92 | 0,84 | 0,82 | 1,06 | 0,86 | 0,98 |
| PODE | 2725 | 0,86 | 0,99 | 1,19 | 1,04 | 1,16 | 0,49 | 1,26 | 0,97 | 0,55 |
| NOVO | 523 | 1,40 | 1,04 | 0,53 | 0,74 | 0,39 | 0,47 | 0,71 | 0,86 | 0,61 |
| Cidadania/PPS | 1842 | 0,96 | 0,93 | 1,30 | 0,78 | 1,03 | 0,40 | 1,30 | 1,21 | 0,78 |
| PV | 1210 | 0,78 | 0,63 | 0,93 | 0,80 | 0,48 | 0,30 | 2,63 | 1,11 | 0,50 |
| Solidariedade | 1385 | 1,15 | 1,16 | 0,92 | 0,79 | 0,79 | 1,32 | 0,77 | 0,84 | 1,09 |

Padrões legíveis (interpretação do agente, a validar): PL, PSL e, em menor grau, DEM/UNIÃO concentram foco em direito penal e segurança; PL e PP/MDB/PT têm foco em estrutura fundiária (que pode ser reforma agrária no PT e regularização/propriedade no PL: o tema não diz qual); PT, PCdoB, PSOL, PDT e PSB se parecem no foco em trabalho e previdência/assistência; PSOL se destaca em direitos humanos e cultura; PV em meio ambiente; NOVO tem pouco foco em segurança, direitos humanos e terra e foco em finanças públicas (1,99, tabela completa em `derived/focus_ratio_2011_2026.json`). Períodos de 1987 a 2010 estão em cada JSON.

Partidos com poucas proposições ficam como `amostra_insuficiente` por período (limite de 100 proposições normativas): PCdoB 1987-94 (88), NOVO, REDE, SOLIDARIEDADE, PODE e PSD antes de existirem.

## Governos ocupados (fato, TSE; 1994 a 2022 para governadores)

Governadores eleitos (soma de 1994-2022) e prefeituras de capitais eleitas (2000-2024): PSDB 45 / 23; MDB 44 / 26; PT 31 / 22; PSB 26 / 17; PFL-DEM-UNIÃO 22 / 16; PDT 9 / 11; PP 10 / 7; PSD 6 / 10; PL-PR 2 / 5; PCdoB 2 / 2; PSOL 0 / 2. Presidentes eleitos: PSDB (1994, 1998), PT (2002, 2010, 2014, 2022), PSL (2018); 2006 não consta no arquivo do TSE (situação nula) e Lula reeleito está registrado pelo CPDOC. Temer (MDB) assumiu pela vice-presidência, não por eleição como titular.

As classificações acadêmicas de cada governo federal, já usadas pelo projeto, são anexadas em `governos_ocupados.presidencia_eleicoes_vencidas` (interpretação acadêmica: classifica o discurso/governo estudado, nunca o partido).

O catálogo de governos estaduais do projeto só cobre SP e RJ com profundidade. **Não há política estadual ou municipal documentada** nos arquivos deste levantamento: só quem governou. Isso é lacuna, não ausência de política.

### Políticas implementadas e a distinção iniciativa / coalizão / herança

Os atos legais ficam sob o partido do presidente filiado na data da sanção (PT 15, PSDB 5, MDB 6, PSL 2, PRN 1, mais atos de presidente sem partido que não são creditados a nenhum). **Isso prova quem governava, não quem teve a iniciativa.** Exemplo verificado: a Lei de Cotas (12.711/2012, sancionada por Dilma, PT) nasceu do PL 73/1999 da deputada Nice Lobão, **PFL-MA**, conforme o arquivo de autores da Câmara de 1999. Bolsa Família, Lei de Responsabilidade Fiscal ou o teto de gastos vieram de governos e coalizões, com votos de partidos além do presidente. Por isso o campo `atribuicao` de cada ato diz "não prova iniciativa do partido". Bolsonaro esteve sem partido entre 11/2019 e 11/2021: atos desse intervalo não são creditados ao PSL nem ao PL.

Os atos com `proposed_direction: null` são contestados no próprio rubric (E5 previdência, E7 regra fiscal, E3 reforma tributária, C4 pacote anticrime) e exigem codificação por incidência.

## Plataformas presidenciais (TSE, 2018 e 2022)

Ocorrências de um léxico explícito por 10 mil palavras (salience, não posição: citar "privatização" para criticá-la conta igual). Resultado completo em `derived/presidential_platform_theme_focus.json`. 2010 e 2014 não foram analisadas porque o número do PDF não corresponde ao SQ_CANDIDATO do TSE (verificado) e a autoria não é comprovável. 1998, 2002 e 2006: o TSE não publica (HTTP 404). O PDF de Ciro Gomes em 2022 tem 1 palavra extraível (PDF de imagem); precisa de OCR.

Exemplos 2018 (mercado / Estado-redistribuição / segurança por 10 mil palavras): Haddad (PT) 6,6 / 21,3 / 21,6; Ciro (PDT) 8,2 / 11,0 / 35,2; Boulos (PSOL) 5,8 / 17,2 / 17,6; Alckmin (PSDB) 29,5 / 36,9 / 51,7 em um texto curto (1.355 palavras); Bolsonaro (PSL) 22,2 / 8,2 / 30,4, com valores tradicionais em 114,5; Amoêdo (NOVO) 20,2 / 13,4 / 17,9.

## Caso PDT (sem conclusão prévia)

**Hipótese da usuária**: direita. **Classificação atual do projeto**: esquerda (3,93 em 2018 e 3,86 em 2022, escala 0-10, esquerda abaixo de 4,5).

Evidências por canal:

1. **Origem e programa (fato, B)**. Fundado em 1980 por Brizola após perder a sigla PTB; manifesto em "defesa da democracia, do nacionalismo e do socialismo"; Carta de Lisboa (1979) com "socialismo democrático"; modelo declarado no socialismo europeu, com desconforto de getulistas. Sete prioridades: infância, trabalhadores, mulheres, negros, indígenas, natureza e recuperação de concessões a estrangeiros lesivas à economia nacional (CPDOC/FGV).
2. **Comportamento legislativo 1984-1993 (fato reportado, B)**. Votou unido pelas Diretas (1984); na Constituinte defendeu temas nacionalistas: jornada de 40 horas, monopólio estatal do petróleo; contra mandato de cinco anos para Sarney; opôs-se às privatizações de Collor (CSN) e aos planos Cruzado e Collor por perda salarial; votou unido contra o Fundo Social de Emergência (1993). Por esses indicadores (E1, E4, E7), de esquerda no vocabulário da rubrica.
3. **Pragmatismo e porosidade (fato reportado, B)**. Brizola aproximou-se de Collor em 1991-92 contra a bancada; César Maia, Saturnino Braga (que foi ao PSB) e Marcelo Alencar (que foi ao PSDB, em 1993) deixaram o partido; o PFL chegou a propor Jaime Lerner (eleito governador do PR pelo PDT em 1994, segundo o TSE) como candidato em aliança. O partido abriga políticos que depois migram para outros campos, inclusive o PSDB.
4. **Estimativas externas (interpretação acadêmica)**. Survey de especialistas: 3,93 (2018) e 3,86 (2022), entre PT (2,97 e 2,68) e PSDB (7,11 e 6,76); PSB 4,05 e 3,59. Survey de legisladores (Power e Zucco, escala 1-10): 3,07; 3,16; 3,12; 3,02; 3,32 em 1990-2005, estável e à direita de PT, PCdoB e PSB (1,7 a 2,9) e à esquerda de PSDB (3,6-5,2). O PDT é, nessas fontes, de centro-esquerda, não de direita. A margem até o limiar de centro (4,5) é de cerca de 0,6 ponto, com desvio-padrão de respondentes de 1,4, de modo que "esquerda" é classificação de limiar, não certeza.
5. **Alianças presidenciais (fato, A)**. Candidato próprio em 1994 (Brizola), 2006 (Cristovam Buarque), 2018 e 2022 (Ciro); na coligação de Lula em 1998 e de Dilma em 2010 e 2014; com Ciro (PPS) e PTB em 2002. **Nunca** esteve, no 1º turno, em coligação encabeçada por PSDB, DEM ou PL. Lacuna: apoio no 2º turno e a base do governo Bolsonaro e do terceiro governo Lula não foram coletados.
6. **Governos (fato, A)**. 9 governadores eleitos de 1994 a 2022 (MT e PR em 1994; RJ em 1998; AP em 2002, 2006, 2014, 2018; MA em 2006; MT em 2014) e 11 prefeituras de capital de 2000 a 2020. Antes, os governos Brizola no Rio (CIEPs, escola de tempo integral) e a eleição de 3 governadores em 1990. A fonte arquivada não avalia resultados dessas políticas.
7. **Foco dos projetos (fato, A; leitura do agente)**. 2011-2026: razão de foco em trabalho 1,16, previdência/assistência 1,23, saúde 1,23, educação 1,21, meio ambiente 1,18; em direito penal 0,75 e defesa/segurança 0,82. É o perfil de PT/PSB/PCdoB, longe do perfil PL/PSL/DEM (1,26 a 1,95 em segurança e penal). Em estrutura fundiária o PDT tem 0,42 (perfil urbano).
8. **Plataforma 2018 (fato, A; salience)**. Ciro (PDT): segurança pública 35,2 por 10 mil palavras, acima de Haddad (21,6) e Boulos (17,6) e próximo de Bolsonaro (30,4); mercado e ajuste fiscal 8,2 (Haddad 6,6; Amoêdo 20,2); Estado indutor/redistribuição 11,0 (Haddad 21,3). Texto de nacional-desenvolvimentismo com ênfase em segurança, não um programa liberal.

**O que as evidências mostram**: contrariam a hipótese de que o PDT seja de direita pelos indicadores de comportamento coletados: políticas defendidas, alianças presidenciais, perfil de projetos, estimativas de especialistas e legisladores. Sustentam centro-esquerda trabalhista-nacionalista, a **mais moderada** do campo de esquerda, com mais ênfase em segurança e menos em temas culturais que PT e PSOL, e com quadros que saem para outros partidos.

**O que pode dar razão à usuária e não foi verificado aqui**: votações nominais recentes (reforma da previdência de 2019, teto de gastos, reforma trabalhista, impeachment de 2016), orientação de bancada e deputados que votaram contra a orientação; alianças estaduais e municipais recentes; participação em governos de cada campo depois de 2022. Esses pontos cabem ao agente de votações e a uma coleta de alianças estaduais. Afirmações sobre trajetória de Ciro Gomes fora do que o TSE e o CPDOC registram (candidaturas por PPS em 1998 e 2002 e por PDT em 2018 e 2022 estão no TSE) são nível C e não foram usadas.

## Caso PCdoB (hoje sem classificação em parte do catálogo)

**Por que o catálogo tem lacuna**: o survey de especialistas tem só duas ondas (2018 e 2022, notas 1,92 e 1,78); outros anos ficam sem classificação por regra de datação, não porque o partido seja ambíguo.

Evidências:

1. **Origem (fato, B)**. Criado em 1962 por dissidentes do PCB com o objetivo declarado de derrubar o capitalismo e instalar o socialismo por revolução; alinhado à China e à Albânia; preparava luta armada (guerrilha do Araguaia). É origem histórica.
2. **Mudanças de programa (fato, B)**. A 8ª Conferência (1985) admitiu capital privado, pluralidade partidária e liberdade de culto e renegou o stalinismo; a partir de 1991 abandonou a Albânia como modelo. Apoiou Tancredo-Sarney em 1985, o impeachment de Collor em 1992, e elegeu constituintes em coligação com o PMDB em 1986.
3. **Alianças (fato, A + B)**. Apoio a Lula/PT em 1989, 1994, 1998, 2002 e 2006 (CPDOC); no TSE, em coligação de Lula/Dilma/Haddad/Lula em 2002, 2006, 2010, 2014, 2018 e 2022 (a fonte do TSE omite o partido em 1994 e 1998, o que o CPDOC corrige). Não consta de nenhuma coligação do campo oposto.
4. **Estimativas externas (interpretação acadêmica)**. Especialistas: 1,92 e 1,78; legisladores (1-10): 1,70; 2,19; 2,15; 1,68; 2,34 em 1990-2005, entre os mais à esquerda do Congresso, junto a PT e PSTU. PSOL tem 1,28 e 1,41 e PCB, PCO e PSTU abaixo de 1: o PCdoB é de esquerda forte, não o ponto mais extremo.
5. **Governos (fato, A)**. 2 governadores eleitos (MA, 2014 e 2018), 2 capitais (Aracaju 2008 e 2016), 10 prefeitos em 2004, 40 em 2008, 54 em 2012, 82 em 2016. Ministério dos Esportes desde 2003 (CPDOC, 2014). Em eleições estaduais apoia candidatos petistas em vez de lançar os seus.
6. **Foco dos projetos (fato, A)**. 2011-2026: trabalho 1,77, cultura 1,52, educação 1,35, previdência/assistência 1,31; baixo em economia (0,66), indústria e comércio (0,71) e meio ambiente (0,43).
7. **Plataforma presidencial própria**: nenhuma; só em coligação (2018 com o programa do PT, 2022 com a federação).

**O que as evidências mostram**: confirmam a hipótese da usuária. Esquerda, em todas as fontes datadas coletadas, de forma consistente por 35 anos. Ressalvas: (i) o partido tem origem revolucionária e a rubrica separa "extremo" por portão democrático (G1-G4), para o qual não encontrei ato recente contrário (nem verifiquei declarações sobre regimes estrangeiros); (ii) os especialistas o põem acima do PSOL e dos partidos trotskistas, portanto a posição "extrema" depende da definição na rubrica, não do rótulo histórico. Recomendação: para os anos sem onda de survey, usar as estimativas de Power e Zucco (1990-2005) e o comportamento (alianças e foco), sem transferir notas.

## Cobertura por partido

Todos os partidos pedidos têm arquivo em `parties/` (PPS e Cidadania agrupados; Rede só com a sigla atual). Históricos 1980-1994: PDS e PRN têm arquivo próprio, e o PFL e o PL antigo estão dentro de suas linhagens. **PDC não ganhou arquivo próprio** (294 proposições na Câmara, abaixo do limite útil).

Partidos sem ato legal creditado (por nunca terem tido presidente da República titular): PDT, PCdoB, PSB, PL/PR, PP, PTB, PSD, Republicanos, PODE, Novo, Cidadania, PV, Rede, Solidariedade, Avante. Para esses, "políticas implementadas" depende de governos estaduais e municipais, não coletados em detalhe. O fato de um partido integrar ministérios ou base do governo está no canal de coligação (apenas 1º turno) e não em cargos de ministérios, que não foram levantados.

## Lacunas conhecidas

- Direção dos projetos de autoria: não codificada (só foco). Uma amostra manual por ementa seria o próximo passo para indicadores sensíveis (E3, E5, E8, C4).
- Senado: sem tema oficial na listagem e só primeiro autor; sem decomposição de "e outros".
- Emendas, discursos e requerimentos além de requerimentos de informação: não coletados (o arquivo da Câmara só traz proposições autorais).
- Câmara 1980-1986 e 1987: arquivos pequenos (1987 tem 316 proposições), tratados como cobertura parcial; períodos começam em 1987.
- TSE: eleição presidencial de 2006 sem situação final; cadeiras de 2002 e 2006 incompletas; prefeituras de capital de 2000 e 2004 incompletas; coligações de 1994 e 1998 incompletas.
- Plataformas: sem 1998-2006 (404); 2010 e 2014 sem vínculo seguro candidato-PDF; PDF de imagem de Ciro 2022; plataformas dos partidos sem candidato presidencial e de governadores (arquivos `proposta_governo_2026_*` já em `data/tse`) não analisadas.
- Políticas estaduais e municipais: sem fonte levantada; catálogo de governos estaduais do projeto só tem SP e RJ.
- Planalto indisponível desta rede (timeout): atos legais verificados pelo LexML, que replica a ementa e o texto.
- Posição de bancada em políticas-chave (voto e orientação): fora do escopo, a cargo do agente de votações.
- Literatura acadêmica adicional (por exemplo sobre PDT, trabalhismo, PCdoB) não foi baixada nesta rodada: as fontes de apoio são CPDOC/FGV, Bolognesi et al., Power e Zucco (já arquivadas pelo projeto) e dados oficiais. Nada foi incluído de memória como se fosse verificado.
