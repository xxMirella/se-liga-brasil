# Senado no governo Itamar Franco: composição e orientação, 1992–1994

Revisão de 28/10/2026. Recorte: 02/10/1992 a 01/01/1995, na 49ª legislatura (as cadeiras de 1986 pertencem às legislaturas 48 e 49). Três fotografias datadas de 31/12 (1992, 1993 e 1994). Código: `src/service/political_dashboard/senate_orientation_1992_1994.py` e `.json`; reconstrução em `scripts/build_senate_orientation_1992_1994.py`; validação em `data/political-dashboard/senate-itamar-1992-1994-validation-20261028.json`. O comportamento de 2026 não foi alterado.

## Conclusão

Em nenhuma das três datas há maioria absoluta (mais de 40 de 81) de direita nem de esquerda pela classificação adotada. Resultado principal (síntese editorial, onda de 1993 de Zucco e Power):

| Data | Direita | Centro | Esquerda | Sem filiação | Partido sem estimativa | Partido não identificado | Total |
|---|---|---|---|---|---|---|---|
| 31/12/1992 | 31 | 26 | 12 | 2 | 3 | 7 | 81 |
| 31/12/1993 | 27 | 27 | 11 | 3 | 0 | 13 | 81 |
| 31/12/1994 | 26 | 23 | 13 | 4 | 0 | 15 | 81 |

O PMDB (rotulado MDB pela API) tinha 26, 27 e 23 cadeiras e a estimativa dele (−0,022 na escala −1 a +1) está praticamente no ponto zero. Só a leitura de todo o MDB como direita produz maioria (57, 54 e 49), o que é um limite superior da sensibilidade e não resultado. Lido como esquerda, o MDB leva a esquerda a 38, 38 e 36, ainda sem maioria. Somando todas as lacunas à direita, a direita chega a 38 (1992), 40 (1993) e 41 (1994); em 1994 a maioria só existiria nesse cenário extremo. Por isso o texto do painel diz "sem maioria de direita nem de esquerda comprovada", e não "sem maioria".

## Fotografias: quem ocupava as 81 cadeiras

A lista nominal completa (UF, cadeira, ocupante, id oficial do Senado, papel, partido, fonte e data da evidência do partido) está nos arquivos de validação. Cada fotografia tem 27 UFs × 3 cadeiras e 81 pessoas distintas. Papéis distintos, sem vagas documentadas:

| Data | Titular | Suplente em exercício | Retorno do titular provável, sem ato | Ocupante ambíguo |
|---|---|---|---|---|
| 31/12/1992 | 68 | 13 | 0 | 0 |
| 31/12/1993 | 69 | 9 | 3 | 0 |
| 31/12/1994 | 68 | 11 | 1 | 1 |

Titular afastado nunca é contado junto com o suplente. "Suplente em exercício" inclui suplentes que ocupam cadeiras de titulares falecidos ou renunciantes (por exemplo Áureo Mello, Hydekel Freitas, João França, Dario Pereira) e Gilberto Miranda, que o dado oficial coloca no exercício de 31/12/1992 após a renúncia de Amazonino Mendes (30/12/1992). Afastamentos e posses relevantes estão em `seat_events` (FHC/Eva Blay, Alexandre Costa/Bello Parga, Hugo Napoleão/Álvaro Pacheco, Coutinho Jorge/Juvêncio Dias, José Eduardo/Luís Alberto de Oliveira, Maurício Corrêa/Pedro Teixeira, Élcio Álvares/Jonice Tristão, Beni Veras/Reginaldo Duarte, Gerson Camata/Joaquim Beato, Iram Saraiva/Jacques Silva). O ambíguo de 1994 é a cadeira de Henrique Almeida (AP), com Airton Oliveira votando em outubro sem relação de chapa na API.

## Partido na data: fontes e hierarquia

1. Intervalo de filiação da API de dados abertos (`/senador/{id}/filiacoes` e `/mandatos`).
2. Rótulo partidário do voto nominal da API em até 150 dias da data.
3. Lista de lideranças partidárias impressa no Diário do Congresso Nacional de 12/04/1994 (só para 1994, 263 dias antes; transcrita à mão da OCR).
4. Cabeçalho partidário impresso nos Anais do mesmo ano (OCR).

Nunca se inferiu partido pelo nome ou por legenda posterior. Origem na fotografia de 1992: 61 intervalos da API, 13 cabeçalhos impressos, 7 lacunas; 1993: 57, 1 voto, 10 cabeçalhos, 13 lacunas; 1994: 55, 1 voto, 7 listas de liderança, 3 cabeçalhos, 15 lacunas. As fontes de menor confiança (texto impresso) saem no cenário `printed_text_claims_excluded` (direita 26, 24 e 21).

## Classificação dos partidos em 1992–1994

O catálogo de 2018/2022 (`political_orientation_catalog`) não cobre esses anos e não foi estendido. A classificação vem da Tabela C1 do suplemento de Zucco e Power (2024), [The Ideology of Brazilian Parties and Presidents](https://doi.org/10.7910/DVN/6KVTUV), estimativas na escala −1 a +1 da onda de 1993, que pesquisou a legislatura de 1991–1995. O PDF foi arquivado em `data/political-orientation/zucco-power-sources/` com SHA-256 `148a7d16…ff69`. Esta é uma síntese editorial: a onda de 1993 é aplicada às três datas, sem interpolar.

Regra de três grupos do Se Liga, Brasil: esquerda abaixo de −0,1, centro de −0,1 a +0,1 inclusive, direita acima de +0,1 (mesma largura proporcional das faixas 4,5 e 5,5 da escala 0–10; não são categorias dos autores). Pontuações usadas: PT −0,830, PSB −0,746, PDT −0,447, PSDB −0,225 (esquerda), MDB −0,022 (centro), PTB 0,482, PFL 0,671 (coluna DEM, mesmo partido), PRN 0,869, PP (1993) 0,339 (direita), PDS e PPR pela série PP 0,734. A pesquisa de 1993 avaliou o item PPR (162 avaliadores) e não o PDS, extinto em abril de 1993; a ligação entre esse item e a coluna PP da Tabela C1 é inferência do projeto (a linha PPB do arquivo de 2009 usa o item PPR em 1993 e tem a mesma ordem relativa). PL (0,643), PCdoB (−0,946) e PPS (−0,597) também têm pontuação, sem cadeiras nas fotografias atuais.

Autodeclaração, estimativas de pesquisa e checagens categóricas (Coppedge, 1997; Mainwaring, Meneguello e Power, 1999) ficam separadas em [partidos-classificacao-fontes-1992-1994.md](partidos-classificacao-fontes-1992-1994.md). A checagem categórica concorda no lado de todos os partidos com cadeira, exceto o PRN, que Coppedge trata como personalista.

Sem classificação, sem virar centro: PDC (a tabela só o traz em 1990, 0,622, e ele se fundiu ao PDS em 1993; entra apenas como sensibilidade), S/Partido (sem filiação) e cadeiras sem partido identificado.

## Sensibilidade (direita / esquerda)

| Cenário | 1992 | 1993 | 1994 |
|---|---|---|---|
| Principal | 31 / 12 | 27 / 11 | 26 / 13 |
| PSDB como centro | 31 / 6 | 27 / 5 | 26 / 5 |
| MDB como direita | 57 / 12 | 54 / 11 | 49 / 13 |
| MDB como esquerda | 31 / 38 | 27 / 38 | 26 / 36 |
| PRN sem classificação (personalista em Coppedge) | 26 / 12 | 23 / 11 | 24 / 13 |
| PDC pela onda de 1990 como direita | 34 / 12 | 27 / 11 | 26 / 13 |
| PDS e PPR sem classificação | 27 / 12 | 22 / 11 | 20 / 13 |
| Sem textos impressos | 26 / 8 | 24 / 8 | 21 / 10 |
| Lacunas à direita | 38 / 12 | 40 / 11 | 41 / 13 |
| Lacunas à esquerda | 31 / 19 | 27 / 24 | 26 / 28 |

## Lacunas

- Não foi localizado relatório ou ata oficial com as 81 cadeiras nessas datas; os relatórios anuais de 1992–1994 não estavam acessíveis. As fotografias são reconstruções.
- O serviço de licenças da API não devolve registros do período; afastamentos vêm de períodos ministeriais, atos citados e votos nominais. Votos de 1992 vão de 14/10 a 11/11 e os de 1994 terminam em 26/10.
- Conflitos preservados: Ney Suassuna (PTB-PB num cabeçalho de 11/03/1993, MDB na API; fora do exercício nas datas), Lavoisier Maia e Júnia Marise (listas impressas divergem da API) e Carlos De' Carli (1537) × Carlos de Carli (1542).
- O banco PostgreSQL não foi consultado: não havia `DATABASE_URL` no ambiente e as credenciais não foram procuradas. Nada foi gravado.
- As fotografias não são a prova de presença diária; "ausência não prova saída" foi respeitado, e por isso titulares sem voto próximo seguem como titulares com a evidência registrada.

## Integração e testes

`timeline.py` usa `senate_1992_1994_cell(year)` apenas para `senado` nos anos 1992–1994; a seção `#senado-1992-1994` de `/fontes-dos-dados` traz os números e as fontes. O card do painel permanece enxuto. Testes: `tests/test_senate_orientation_1992_1994.py` (soma 81, três cadeiras por UF, sem maioria, sem classificação diferente de centro, ressalvas, sensibilidade e preservação de 2026).
