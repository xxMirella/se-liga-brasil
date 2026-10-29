# Coleta oficial do histórico do Senado (1992–1994)

Referência: 28/10/2026. Coleta somente de leitura, sem acesso ao banco. Tudo fica em `data/` (ignorado pelo git).

## O que foi arquivado

Diretório `data/political-dashboard/senate-history-1992-1994-source/` com `manifest.json` (`url`, `endpoint`, `kind`, `senator_id`, `http_status`, `baixado_em`, `sha256`, `bytes`, `path`) e os bytes originais em `raw/`.

| Item | Resultado |
|---|---|
| Pessoas | 91 ocupantes das três fotografias e 5 do inventário de pesquisa fora delas (Amazonino Mendes 82, Carlos de Carli 1542, Airton Oliveira 3233, Ney Suassuna 63, José Agripino 40): 96 |
| Endpoints por pessoa | `/senador/{id}.json`, `/mandatos.json`, `/filiacoes.json`, `/licencas.json` |
| Listas | legislaturas 47, 48, 49, `48/49` e `senador/partidos.json` (catálogo com criação/extinção) |
| Respostas | 389, todas HTTP 200 (nenhum 404, 429 ou 5xx), 1,3 MB |
| Ritmo | sequencial, 0,7 s entre pedidos (cerca de 1,4 req/s), User-Agent identificável, backoff para 429/5xx |
| TSE | `consulta_cand_1994.zip` (1,27 MB, sha256 `98d72c20…63dcc`); 1990 e 1986 retornam 404, registrados em `tse/manifest.json` |

Não existe endpoint de composição por data nem de sucessão partidária no serviço. `/senador/partidos` redireciona para `ListaPartidos.json`.

Scripts: `scripts/collect_senate_history_1992_1994.py`, `scripts/normalize_senate_history_1992_1994.py` e `scripts/match_tse_1994_senate_history.py` (ruff limpo). Saídas em `data/political-dashboard/`:

- `senate-history-1992-1994-normalized.json`: por senador, identidade, mandatos (legislaturas, titular/suplente, exercícios com causa), filiações (intervalo com fim inclusivo da fonte e fim exclusivo, URL e sha256) e partidos históricos.
- `senate-history-1992-1994-inventory-comparison.json`: 243 linhas data-cadeira comparadas com o inventário.
- `senate-history-1992-1994-tse-1994-matches.json`: candidaturas de 1994 por nome civil e nascimento.

## Resultado da comparação

| Data | Cadeiras com filiação datada cobrindo a data | Concordam com o inventário | Conflitos | Sem intervalo da API |
|---|---|---|---|---|
| 31/12/1992 | 61 de 81 | 61 | 0 | 20 |
| 31/12/1993 | 57 de 81 | 57 | 0 | 24 |
| 31/12/1994 | 55 de 81 | 55 | 0 | 26 |

- A API confirma exatamente as 61, 57 e 55 cadeiras que o inventário já tinha pelo intervalo da API. Não traz nenhuma informação nova para o período.
- "Partido não identificado" (7, 13 e 15): a API resolve 0, 0 e 0. Nenhum desses ocupantes tem filiação datada que cubra a data.
- Dos 20, 24 e 26 sem intervalo, 13, 11 e 11 já tinham partido por texto impresso ou voto. Não há contradição, apenas corroboração faltando.
- 68 pessoas têm filiação cobrindo ao menos uma data, 48 cobrem as três e 23 de 91 não cobrem nenhuma.
- Filiações: 229, das quais 36 sem datas (12 ocupantes só têm filiação sem data, por exemplo Eva Blay, Henrique Almeida, Nelson Carneiro, Pedro Teixeira, Dario Pereira). Filiação sem data nunca é tratada como cobertura.

### Por que as lacunas permanecem

- Último intervalo termina antes da data e não há seguinte: Alfredo Campos (MDB até 15/08/1989), Mansueto de Lavor (MDB até 21/10/1988), José Richa (MDB até 28/06/1988), Jarbas Passarinho (PDS até 15/10/1990), Meira Filho (PFL até 04/03/1993), Hydekel Freitas (PFL até 25/10/1993), Irapuan Costa Júnior (MDB até 04/02/1993).
- Em 16/06/1993, PDS, PDC e PTB fecham filiações de vários senadores (Carlos De' Carli PTB, Moisés Abrão PDC, Louremberg Nunes PDS) sem a filiação seguinte. A fonte não diz sucessão, então PPR não foi deduzido.
- Alexandre Costa (2) e Gerson Camata (28): só filiações a partir de 01/02/1995.
- Almir Gabriel: PSDB até 15/12/1994, não cobre 31/12.
- Sem nenhuma filiação ou só sem data: Juvêncio Dias (136), Eva Blay, Pedro Teixeira, João Calmon, Francisco Rollemberg, Fernando Henrique Cardoso, Nelson Carneiro.

## Casos pedidos

- **Ney Suassuna (63, fora das fotografias)**: API: MDB de 13/01/1993 a 21/05/1993 e S/Partido de 22/05/1993 a 01/01/1995. O cabeçalho "PTB-PB" de 11/03/1993 não tem PTB na API. O conflito é real e permanece aberto.
- **Lavoisier Maia (799)**: S/Partido de 22/03/1989 a 31/01/1999 (antes PDS até 21/03/1989). Coincide com o inventário. A divergência é com a lista impressa, que a API não resolve.
- **Júnia Marise (51)**: PRN até 20/02/1994 e PDT de 21/02/1994 a 31/01/1999. O inventário já usava esse intervalo; a divergência com a lista impressa não é resolvida pela API.
- **Carlos De' Carli (1537) × Carlos de Carli (1542)**: a API traz nomes civis e nascimentos diferentes (Carlos Alberto De' Carli, 08/05/1941, titular AM 1987–1995, PTB até 16/06/1993; Carlos Antônio de Carli, 09/05/1948, mandato 1991–1999 sem participação e filiações PFL e MDB sem data). São pessoas distintas na fonte. Em 1993 e 1994, o 1537 fica sem partido após 16/06/1993.
- **Henrique Almeida (1737), AP, 1994**: a API tem PFL sem data, um mandato sem código e o mandato 427 "Titular" 1991–1999, sem exercícios nem licenças. Não resolve a ocupação da cadeira em 1994. Airton Oliveira (3233) só tem mandato 1991–1995 sem participação e nenhuma filiação.
- **Licenças**: nenhum registro de licença iniciado entre 1991 e 1994 para as 96 pessoas. Exercícios aparecem em 31 de 141 mandatos das legislaturas 48/49. A API não preenche os afastamentos do período.

## Partidos históricos

28 combinações sigla/código encontradas nas filiações, ligadas ao catálogo pelo código (nunca por sigla ou nome). Há siglas com códigos diferentes: MDB 33 (1980, sem extinção) e MDB 240 (1965–1979, usado em filiações antigas); PP 38 (1993–1995) e PP 418 (Progressistas, 2003); PSD 89 (1987–2003) e PSD 557 (2011). Datas de criação do catálogo: PDS 01/01/1980 a 16/06/1993, PDC 30/03/1985 a 16/06/1993, PFL 24/01/1985 a 02/08/2007, PRN 22/02/1989 a 08/06/2001, PP 31/01/1993 a 25/10/1995, PPR 01/04/1993 a 25/10/1995. O catálogo da API rotula como MDB o PMDB de 1987–1994; a sucessão MDB/PMDB e PDS+PDC para PPR não é declarada por nenhum endpoint, então `succession` fica nulo. Uma filiação sem sigla ("Partido Democrático Universitário da Bahia", Nelson Carneiro) também aparece sem código nem datas.

## TSE 1994

`consulta_cand_1994` (BRASIL.csv) tem 232 candidaturas a senador. Por nome civil e nascimento iguais, 51 das 96 pessoas aparecem. Para 9 dos 15 "não identificados" de 1994 há partido de candidatura: João Calmon PMDB, Alexandre Costa PFL, Saldanha Derzi PP, Almir Gabriel PSDB, Jarbas Passarinho PPR, Nelson Carneiro PP, Hydekel Freitas PPR, Francisco Rollemberg PMN, Fernando Henrique Cardoso PSDB. Sem resolução para Carlos De' Carli, Meira Filho, Alfredo Campos, Louremberg Nunes, José Richa e Paulo Bisol. O partido de candidatura é de agosto a outubro de 1994, não de 31/12/1994, então serve como evidência com escopo `electoral:1994`, não como intervalo. Para os seis com partido no inventário e candidatura, as siglas coincidem (PMDB vs MDB tratadas como rótulos). Para 1990, o TSE não publica arquivo (404).

## Lacunas

- A API não resolve nenhum dos 7, 13 e 15 "partido não identificado" nem as lacunas de 1993 e 1994 após a extinção de PDS e PDC.
- Sem sucessão partidária em fonte oficial; sem composição por data; sem licenças do período.
- Sem candidaturas de 1990 (TSE 404). Atas, relatórios anuais e Diário do Congresso não foram obtidos por esta frente.
- Os conflitos de Ney Suassuna, Lavoisier Maia e Júnia Marise com os textos impressos continuam sem arbitragem; a API apenas fixa o lado dela.
