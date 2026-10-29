# Posição dos partidos nas votações nominais do Legislativo federal

Objetivo: medir **comportamento** (como cada partido votou, com a filiação vigente na data do voto) em vez de discurso. Este documento descreve dados, escolhas, resultados e limites do módulo `src/service/party_vote_analysis/`. Os resultados completos estão em `data/political-orientation/party-model/votes/party_vote_positions.json` (não versionado; `data/` está no `.gitignore`).

## 1. Dados e reprodução

| Etapa | Comando | Saída |
|---|---|---|
| Download educado e retomável | `.venv/bin/python scripts/download_party_vote_archives.py --chamber camara` e `--chamber senado` | `votes/raw/` + `manifest.json` (arquivo, url, ano, tipo, sha256, bytes, baixado_em, retained) |
| Normalização em streaming | `.venv/bin/python scripts/normalize_party_vote_archives.py` | `votes/normalized/{camara,senado}/votings-AAAA.jsonl`, `votes-AAAA.csv.gz`, `orientations-AAAA.jsonl` |
| Posições | `.venv/bin/python scripts/build_party_vote_positions.py --replicates 200` | `votes/party_vote_positions.json` |

- **Câmara**: arquivos anuais oficiais `https://dadosabertos.camara.leg.br/arquivos/{votacoes,votacoesVotos,votacoesProposicoes,votacoesOrientacoes}/csv/*-AAAA.csv`, 1991–2026 sondados. `votacoesVotos` existe só a partir de **2001** (2001–2002 com poucas votações nominais); 1991–2000 retornam 404 e ficam registrados no manifest como indisponíveis. `votacoesOrientacoes` existe a partir de 2003.
- **Senado**: `https://legis.senado.leg.br/dadosabertos/votacao?dataInicio=AAAA-01-01&dataFim=AAAA-12-31`, 1991–2026, um arquivo por ano com os votos embutidos. O endpoint antigo `plenario/lista/votacao` está depreciado e, nas verificações feitas (2015), devolvia o mesmo conjunto esparso.
- **Ritmo**: uma requisição por vez, pausa mínima de 1 s (crescente nas novas tentativas), User-Agent identificado, até 4 tentativas, e retomada pelo manifest (nada é baixado duas vezes).
- **Limite de 50 MB**: os arquivos `votacoesVotos` de 2020, 2021, 2022 e 2025 (53, 107, 66 e 58 MB) foram baixados em streaming, tiveram o hash calculado, foram processados em streaming e, depois, **os bytes foram descartados**; o manifest guarda URL, sha256 e bytes com `retained=false`. Os demais originais (cerca de 600 MB) estão preservados. Os arquivos `votacoesObjetos` não foram baixados (grandes e desnecessários: o vínculo votação-proposição vem de `votacoesProposicoes`).
- O banco de dados não foi usado nem alterado.

## 2. Quais votações entram

**Votação de texto principal** (regra textual, independente de como os partidos votaram; `merit_selection.py`):

- Câmara: plenário (`PLEN`) com votos nominais, cuja descrição começa por Aprovado/Rejeitado e cita projeto, PEC, medida provisória, substitutivo ou texto-base. A fórmula "ressalvados os destaques" identifica a votação do texto-base. Ficam fora requerimentos, emendas isoladas, destaques, "mantido/suprimido o texto", redação final, urgência, preferência e pareceres.
- Senado: plenário, votação não secreta, matéria PEC/PL/PLC/PLS/PLV/PLP/MPV, descrição que não comece por Emenda/Destaque/Requerimento.
- "Sim" é sempre apoio ao texto votado. Voto "Votou" do Senado (votação secreta, sem conteúdo publicado) é tratado como estado não direcional.

**Votações temáticas** (`thematic_catalog.py`, 35 itens): cada item exige identidade da proposição (casa, tipo, número, ano) **e** uma palavra-guarda na ementa oficial. Para cada item e casa é usada a votação com mais parlamentares registrados.

**Direção do "sim"**: vem de `data/political-orientation/party-model/rubric.json` (status `PROPOSTA_PARA_APROVACAO`). Cada item aponta para um indicador (E1-E9 econômico, C1-C9 sociocultural) e declara se o "sim" aproxima do polo positivo (+1: mercado, restrição, tradição/autoridade) ou negativo (-1: Estado, redistribuição, ampliação de direitos). Os polos e as fontes (`direction_basis`: V-Party codebook, Manifesto Project, Marks et al. 2006, Coppedge 1997 etc.) são os do rubric, não uma intuição própria. A regra não usa o voto de nenhum partido. O escore de cada votação é `2*parte_pro_polo_positivo - 1`, média dentro do indicador e depois entre indicadores, como em `aggregation` do rubric.

**Temas pedidos e não classificados** (`EXCLUDED_THEMES`): autonomia do Banco Central (o rubric não tem indicador monetário), reforma tributária PEC 45/2019 (sem direção inequívoca), salário mínimo (votos sobre valores), aborto e casamento/LGBT (nenhuma votação nominal de mérito em plenário; só urgência no PL 1904/2024), impeachment 2016 (não é política pública; status de governo é descritor N1, nunca esquerda-direita). Reforma da previdência de 2017 (PEC 287/2016) nunca foi votada em plenário.

**Itens com votação nominal encontrada**: 28 votações temáticas selecionadas ao todo (Câmara e Senado), nas legislaturas 52 a 57:

| Casa | Legislatura | Itens |
|---|---|---|
| Câmara | 52 | biossegurança 2005 |
| Câmara | 54 | Código Florestal 2011, PEC das domésticas 2012 |
| Câmara | 55 | MP 665/2014, maioridade penal (PEC 171/1993), teto de gastos 2016, terceirização (PL 4302/1998), reforma trabalhista 2017 |
| Câmara | 56 | previdência 2019, liberdade econômica, armas 2019, saneamento, licenciamento ambiental, Eletrobras, agrotóxicos |
| Câmara | 57 | marco temporal |
| Senado | 52 | biossegurança 2004 |
| Senado | 54 | Código Florestal, PEC das domésticas |
| Senado | 55 | reforma trabalhista |
| Senado | 56 | previdência 2019, saneamento, PEC da Transição |
| Senado | 57 | marco temporal, saidinha, PEC das drogas, cotas em concursos, licenciamento ambiental |

Muitos itens do catálogo não aparecem porque a votação foi simbólica (sem votos nominais), porque a Câmara só publica votos nominais dessa fase a partir de 2003, ou porque o número ou a ementa não coincidiu com a guarda (a guarda existe justamente para que um número errado nunca entre calado). A cobertura temática é fina: **uma a sete votações por legislatura e dimensão**. Por isso o escore temático traz sempre o número de votações e deve ser lido junto com o intervalo.

## 3. Métricas

1. **Filiação no voto**: a unidade é o par (parlamentar, partido-na-data-do-voto). Quem troca de partido vira duas linhas, cada uma estimada só com os votos dados naquela filiação. O partido nunca é o atual. Siglas não são unificadas por fusão ou renomeação (PMDB e MDB, PFL e DEM, PPS e CIDADANIA ficam separados quando a fonte os separa).
2. **% de sim e coesão (Rice)** por partido e votação: `|sim - não| / (sim + não)`, média sobre votações com ao menos 5 votantes diretivos. Também: taxas de obstrução e de abstenção.
3. **Escore temático** por partido, por dimensão (economic/sociocultural), em [-1, +1] com intervalo de 95% por bootstrap (1000 réplicas: reamostra votações e redesenha a divisão sim/não de cada partido por binomial em torno da divisão observada). Valores com 1-2 votações são indicativos, não estimativas.
4. **Posição ideal em 2 dimensões (PCA com EM)**: matriz parlamentar x votação com +1, -1 e NaN (ausência, abstenção, obstrução, presente sem voto, presidência). Remove votações com minoria abaixo de 2,5% ou menos de 10 votantes e linhas com menos de 15 votos diretivos. Valores ausentes são imputados iterativamente pelo posto 2 (8 iterações). Não é W-NOMINATE: não há modelo de utilidade, termo de erro nem classificação ótima. A posição do partido é a média das linhas dele; a unidade é o desvio-padrão das linhas da legislatura, comparável **apenas dentro da mesma casa e legislatura**. Incerteza: bootstrap das colunas (votações) com realinhamento de sinal e de ordem das dimensões e reamostragem de membros dentro do partido (200 réplicas).
5. **Sinal da dimensão 1**: PCA não tem sinal. Âncora temática quando |correlação| >= 0,4 entre a dimensão e os votos temáticos orientados pelo rubric (Câmara 55 e 56, Senado 56). As demais legislaturas recebem o sinal por **continuidade de membros**: correlação dos escores individuais de quem está presente em duas legislaturas vizinhas (>= 30 pessoas, |r| >= 0,3); o sinal é gravado em `first_dimension_orientation`. Sem vizinha utilizável, `unoriented`.
6. **Alinhamento ao governo** (Câmara): maioria do partido (>= 5 votantes) comparada à orientação "Governo" da própria Câmara, por governo (cronologia presidencial em `legislatures.py`). Mede comportamento frente ao governo do dia, **não ideologia** (descritor N1 do rubric). Também: fração dos membros que seguiu a orientação do líder do próprio partido.

## 4. Resultados

As tabelas abaixo foram geradas de `party_vote_positions.json` (200 réplicas, semente fixa). D1 = primeira dimensão; Rice = coesão média; Gov.* = concordância da maioria do partido com a orientação do governo, por governo, quando há 5 ou mais votações comparáveis (só existe orientação "Governo" nos dados de 2020 em diante).

### Cobertura por ano (votações de texto principal com votos nominais mantidas)

| Ano | Câmara bruto | Câmara votações | Câmara votos | Senado bruto | Senado votações | Senado votos | Com item temático (candidatas) C/S |
|---|---|---|---|---|---|---|---|
| 1991 | não | 0 | 0 | sim | 14 | 715 | 0/0 |
| 1992 | não | 0 | 0 | sim | 1 | 43 | 0/0 |
| 1993 | não | 0 | 0 | sim | 64 | 3454 | 0/0 |
| 1994 | não | 0 | 0 | sim | 3 | 142 | 0/0 |
| 1995 | não | 0 | 0 | sim | 1 | 81 | 0/0 |
| 1996 | não | 0 | 0 | sim | 1 | 81 | 0/0 |
| 1997 | não | 0 | 0 | sim | 3 | 243 | 0/0 |
| 1998 | não | 0 | 0 | sim | 5 | 405 | 0/0 |
| 1999 | não | 0 | 0 | sim | 25 | 2024 | 0/0 |
| 2000 | não | 0 | 0 | sim | 40 | 3236 | 0/0 |
| 2001 | sim | 0 | 0 | sim | 50 | 4034 | 0/0 |
| 2002 | sim | 4 | 1545 | sim | 37 | 2992 | 0/0 |
| 2003 | sim | 10 | 4028 | sim | 53 | 4293 | 0/0 |
| 2004 | sim | 12 | 4522 | sim | 30 | 2428 | 0/1 |
| 2005 | sim | 10 | 3491 | sim | 29 | 2349 | 1/0 |
| 2006 | sim | 14 | 5792 | sim | 27 | 2187 | 0/0 |
| 2007 | sim | 12 | 4345 | sim | 32 | 2592 | 0/0 |
| 2008 | sim | 6 | 2123 | sim | 45 | 3638 | 0/0 |
| 2009 | sim | 17 | 6324 | sim | 45 | 3643 | 0/0 |
| 2010 | sim | 7 | 2387 | sim | 27 | 2187 | 0/0 |
| 2011 | sim | 10 | 3931 | sim | 49 | 3967 | 1/2 |
| 2012 | sim | 16 | 6068 | sim | 29 | 2349 | 3/0 |
| 2013 | sim | 23 | 8860 | sim | 51 | 4131 | 0/2 |
| 2014 | sim | 24 | 8752 | sim | 30 | 2430 | 0/0 |
| 2015 | sim | 52 | 22093 | sim | 5 | 405 | 3/0 |
| 2016 | sim | 18 | 7336 | sim | 2 | 161 | 2/0 |
| 2017 | sim | 22 | 8625 | sim | 61 | 4937 | 2/3 |
| 2018 | sim | 11 | 3975 | sim | 26 | 2106 | 0/0 |
| 2019 | sim | 29 | 11731 | sim | 54 | 4345 | 5/11 |
| 2020 | sim | 29 | 12991 | sim | 119 | 9626 | 0/1 |
| 2021 | sim | 101 | 43010 | sim | 130 | 10527 | 4/0 |
| 2022 | sim | 84 | 33518 | sim | 79 | 6392 | 1/3 |
| 2023 | sim | 50 | 20905 | sim | 45 | 3645 | 1/3 |
| 2024 | sim | 37 | 15349 | sim | 56 | 4536 | 0/5 |
| 2025 | sim | 70 | 28738 | sim | 52 | 4212 | 0/1 |
| 2026 | sim | 25 | 10928 | sim | 22 | 1782 | 0/0 |

### Posições por partido (dimensão 1 em desvios-padrão da legislatura; IC95% por bootstrap)

Somente partidos com 8 ou mais linhas membro-partido. Econ/Soc = escore temático em [-1,+1] (nº de votações entre parênteses); `—` = sem votação temática da dimensão.


**Camara — 52ª legislatura (2003–2006)**: 46 votações, 1 temáticas, 513 linhas, variância explicada D1/D2 = 0.44/0.18, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 92 | -0.89 [-1.24, -0.56] | — | -0.44 (1) | 0.93 | — |
| PL | 43 | -0.65 [-0.88, -0.10] | — | -0.94 (1) | 0.96 | — |
| PTB | 45 | -0.44 [-0.75, +0.06] | — | -0.68 (1) | 0.92 | — |
| PCdoB | 9 | -0.36 [-0.98, +0.45] | — | +1.00 (1) | 0.94 | — |
| PSB | 24 | -0.32 [-0.67, +0.10] | — | -0.57 (1) | 0.91 | — |
| PP | 50 | -0.18 [-0.49, +0.11] | — | -0.81 (1) | 0.83 | — |
| PPS | 20 | +0.17 [-0.33, +0.82] | — | -1.00 (1) | 0.89 | — |
| PMDB | 82 | +0.22 [-0.06, +0.63] | — | -0.76 (1) | 0.84 | — |
| PSDB | 54 | +0.92 [+0.25, +1.32] | — | -0.85 (1) | 0.81 | — |
| PDT | 15 | +1.08 [+0.18, +1.66] | — | -0.80 (1) | 0.84 | — |
| PFL | 62 | +1.26 [+0.57, +1.72] | — | -0.93 (1) | 0.88 | — |

**Camara — 53ª legislatura (2007–2010)**: 42 votações, 0 temáticas, 488 linhas, variância explicada D1/D2 = 0.57/0.15, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 79 | -0.76 [-0.94, -0.50] | — | — | 0.98 | — |
| PR | 39 | -0.75 [-0.90, -0.44] | — | — | 0.97 | — |
| PCdoB | 12 | -0.64 [-0.99, +0.09] | — | — | 0.96 | — |
| PP | 38 | -0.57 [-0.76, -0.38] | — | — | 0.92 | — |
| PMDB | 91 | -0.44 [-0.64, -0.11] | — | — | 0.94 | — |
| PTB | 21 | -0.38 [-0.68, +0.08] | — | — | 0.94 | — |
| PDT | 25 | -0.38 [-0.62, +0.02] | — | — | 0.93 | — |
| PSB | 28 | -0.33 [-0.61, +0.31] | — | — | 0.91 | — |
| PSC | 12 | -0.28 [-0.64, +0.08] | — | — | 0.88 | — |
| PV | 14 | -0.02 [-0.44, +0.59] | — | — | 0.92 | — |
| PPS | 13 | +0.88 [+0.22, +1.56] | — | — | 0.87 | — |
| DEM | 47 | +1.48 [+0.81, +1.94] | — | — | 0.88 | — |
| PSDB | 54 | +1.90 [+1.19, +2.45] | — | — | 0.95 | — |

**Camara — 54ª legislatura (2011–2014)**: 73 votações, 2 temáticas, 605 linhas, variância explicada D1/D2 = 0.31/0.23, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 97 | -1.50 [-2.10, -0.69] | -1.00 (1) | +0.12 (1) | 0.92 | — |
| PROS | 17 | -0.63 [-1.20, +0.10] | — | — | 0.97 | — |
| PV | 11 | -0.51 [-1.34, +0.25] | -1.00 (1) | -1.00 (1) | 0.94 | — |
| PCdoB | 15 | -0.48 [-1.08, +0.23] | -1.00 (1) | +1.00 (1) | 0.95 | — |
| PSB | 35 | -0.39 [-0.94, +0.14] | -1.00 (1) | +0.80 (1) | 0.90 | — |
| PRB | 12 | -0.23 [-0.92, +0.36] | -1.00 (1) | +1.00 (1) | 0.97 | — |
| PR | 38 | -0.05 [-0.46, +0.37] | -0.88 (1) | +0.88 (1) | 0.92 | — |
| PDT | 27 | +0.06 [-0.38, +0.76] | -1.00 (1) | +0.62 (1) | 0.90 | — |
| PTB | 22 | +0.11 [-0.47, +0.69] | -1.00 (1) | +1.00 (1) | 0.91 | — |
| PMDB | 89 | +0.16 [-0.50, +0.82] | -1.00 (1) | +1.00 (1) | 0.94 | — |
| PP | 45 | +0.18 [-0.39, +0.82] | -0.91 (1) | +1.00 (1) | 0.91 | — |
| PSC | 19 | +0.25 [-0.35, +1.07] | -1.00 (1) | +0.89 (1) | 0.92 | — |
| PSD | 56 | +0.25 [-0.28, +0.78] | -1.00 (1) | — | 0.93 | — |
| SDD | 13 | +0.37 [-0.14, +1.01] | — | — | 0.93 | — |
| PPS | 11 | +1.38 [-0.07, +2.30] | -1.00 (1) | +0.67 (1) | 0.91 | — |
| PSDB | 55 | +1.44 [+0.30, +2.54] | -1.00 (1) | +0.96 (1) | 0.90 | — |
| DEM | 28 | +1.83 [+0.58, +2.65] | -1.00 (1) | +1.00 (1) | 0.92 | — |

**Camara — 55ª legislatura (2015–2018)**: 103 votações, 5 temáticas, 662 linhas, variância explicada D1/D2 = 0.38/0.18, orientação: thematic_anchor

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 67 | -1.97 [-2.18, -1.68] | -0.35 (4) | -0.97 (1) | 0.92 | — |
| PCdoB | 17 | -1.94 [-2.25, -1.44] | -0.44 (4) | -1.00 (1) | 0.96 | — |
| PDT | 26 | -0.77 [-1.06, -0.34] | -0.72 (4) | -0.78 (1) | 0.81 | — |
| PROS | 19 | -0.38 [-0.77, +0.00] | +0.07 (4) | -0.33 (1) | 0.76 | — |
| PSB | 42 | -0.09 [-0.47, +0.36] | -0.03 (4) | -0.27 (1) | 0.73 | — |
| PHS | 9 | -0.02 [-0.58, +0.42] | -0.14 (4) | -0.20 (1) | 0.81 | — |
| PV | 12 | +0.01 [-0.45, +0.40] | +0.25 (4) | -0.43 (1) | 0.73 | — |
| PTN | 14 | +0.02 [-0.47, +0.40] | +0.61 (4) | +0.00 (1) | 0.75 | — |
| PRB | 25 | +0.25 [-0.14, +0.55] | +0.58 (4) | +1.00 (1) | 0.83 | — |
| PR | 47 | +0.31 [-0.05, +0.53] | +0.68 (4) | +0.88 (1) | 0.83 | — |
| PPS | 13 | +0.37 [-0.13, +0.89] | -0.27 (4) | -0.45 (1) | 0.86 | — |
| PSC | 15 | +0.44 [+0.03, +0.84] | +0.34 (4) | +0.64 (1) | 0.79 | — |
| PMDB | 81 | +0.48 [+0.07, +0.64] | +0.74 (4) | +0.43 (1) | 0.82 | — |
| SD | 20 | +0.49 [+0.12, +0.92] | -0.01 (4) | +0.41 (1) | 0.79 | — |
| PTB | 25 | +0.49 [+0.09, +0.72] | +0.46 (4) | +0.52 (1) | 0.80 | — |
| PSD | 47 | +0.49 [+0.24, +0.65] | +0.74 (4) | +0.88 (1) | 0.79 | — |
| PP | 53 | +0.60 [+0.37, +0.77] | +0.54 (4) | +0.84 (1) | 0.80 | — |
| DEM | 31 | +0.81 [+0.55, +1.07] | +0.44 (4) | +0.81 (1) | 0.84 | — |
| PSDB | 59 | +0.88 [+0.60, +1.29] | +0.24 (4) | +0.80 (1) | 0.85 | — |

**Camara — 56ª legislatura (2019–2022)**: 243 votações, 7 temáticas, 794 linhas, variância explicada D1/D2 = 0.58/0.10, orientação: thematic_anchor

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PSOL | 11 | -2.36 [-2.53, -2.14] | -1.00 (4) | -1.00 (3) | 0.97 | Bolsonaro 26% |
| PT | 60 | -2.13 [-2.31, -1.89] | -1.00 (4) | -1.00 (3) | 0.97 | Bolsonaro 35% |
| PCdoB | 9 | -2.02 [-2.24, -1.75] | -1.00 (4) | -1.00 (3) | 0.97 | Bolsonaro 42% |
| PSB | 38 | -1.17 [-1.51, -0.85] | -0.28 (4) | -0.47 (3) | 0.78 | Bolsonaro 58% |
| PDT | 32 | -1.08 [-1.32, -0.83] | -0.20 (4) | -0.48 (3) | 0.85 | Bolsonaro 58% |
| CIDADANIA | 10 | +0.23 [-0.03, +0.48] | +0.95 (4) | +0.55 (3) | 0.87 | Bolsonaro 96% |
| AVANTE | 8 | +0.26 [-0.35, +0.77] | +0.68 (4) | +0.44 (3) | 0.84 | Bolsonaro 100% |
| PODE | 17 | +0.32 [-0.02, +0.59] | +0.67 (4) | +0.61 (3) | 0.83 | Bolsonaro 100% |
| NOVO | 8 | +0.37 [+0.08, +0.71] | +0.67 (4) | +1.00 (3) | 0.97 | Bolsonaro 88% |
| PSDB | 39 | +0.42 [+0.25, +0.58] | +0.84 (4) | +0.45 (3) | 0.87 | Bolsonaro 100% |
| UNIÃO | 68 | +0.45 [+0.30, +0.56] | — | — | 0.91 | — |
| PSD | 64 | +0.47 [+0.35, +0.58] | +0.77 (4) | +0.74 (3) | 0.90 | Bolsonaro 100% |
| PROS | 13 | +0.48 [+0.23, +0.67] | +0.57 (4) | +0.44 (3) | 0.87 | Bolsonaro 100% |
| SOLIDARIEDADE | 16 | +0.48 [+0.19, +0.73] | +0.90 (4) | +0.91 (3) | 0.93 | Bolsonaro 100% |
| MDB | 48 | +0.54 [+0.43, +0.64] | +0.92 (4) | +0.75 (3) | 0.92 | Bolsonaro 100% |
| PSC | 17 | +0.61 [+0.43, +0.79] | +0.79 (4) | +0.81 (3) | 0.90 | Bolsonaro 100% |
| PTB | 14 | +0.64 [+0.49, +0.80] | +0.97 (4) | +0.80 (3) | 0.92 | Bolsonaro 100% |
| DEM | 31 | +0.65 [+0.49, +0.74] | +0.95 (4) | +0.96 (3) | 0.91 | Bolsonaro 100% |
| PP | 65 | +0.65 [+0.53, +0.74] | +0.88 (4) | +0.86 (3) | 0.95 | Bolsonaro 100% |
| REPUBLICANOS | 57 | +0.66 [+0.53, +0.76] | +0.96 (2) | +0.79 (3) | 0.96 | Bolsonaro 100% |
| PL | 96 | +0.71 [+0.59, +0.79] | +0.85 (4) | +0.97 (3) | 0.94 | Bolsonaro 100% |
| PSL | 55 | +0.82 [+0.70, +0.93] | +1.00 (4) | +0.99 (3) | 0.88 | Bolsonaro 100% |

**Camara — 57ª legislatura (2023–2026)**: 182 votações, 1 temáticas, 641 linhas, variância explicada D1/D2 = 0.53/0.15, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 71 | -1.10 [-1.26, -0.95] | — | -1.00 (1) | 0.97 | Lula III 99% |
| PCdoB | 9 | -1.06 [-1.23, -0.86] | — | -1.00 (1) | 0.97 | Lula III 96% |
| PDT | 20 | -0.85 [-0.98, -0.74] | — | -0.87 (1) | 0.92 | Lula III 94% |
| PSB | 19 | -0.76 [-0.92, -0.61] | — | -0.60 (1) | 0.88 | Lula III 96% |
| PSOL | 15 | -0.74 [-1.05, -0.41] | — | -1.00 (1) | 0.98 | Lula III 84% |
| AVANTE | 8 | -0.41 [-0.79, +0.11] | — | +0.14 (1) | 0.83 | Lula III 92% |
| PSD | 61 | -0.24 [-0.38, -0.07] | — | +0.52 (1) | 0.82 | Lula III 91% |
| PODE | 22 | -0.16 [-0.42, +0.11] | — | +0.40 (1) | 0.83 | Lula III 92% |
| REPUBLICANOS | 59 | -0.14 [-0.31, +0.03] | — | +0.78 (1) | 0.89 | Lula III 89% |
| MDB | 52 | -0.09 [-0.27, +0.13] | — | +0.47 (1) | 0.80 | Lula III 93% |
| PSDB | 17 | -0.08 [-0.38, +0.29] | — | +0.67 (1) | 0.78 | Lula III 91% |
| PP | 61 | -0.00 [-0.22, +0.23] | — | +0.80 (1) | 0.79 | Lula III 92% |
| UNIÃO | 73 | +0.16 [-0.07, +0.38] | — | +0.92 (1) | 0.71 | Lula III 90% |
| PL | 116 | +1.37 [+1.20, +1.55] | — | +0.98 (1) | 0.78 | Lula III 55% |

**Senado — 52ª legislatura (2003–2006)**: 139 votações, 1 temáticas, 103 linhas, variância explicada D1/D2 = 0.49/0.12, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 15 | -0.97 [-1.28, -0.56] | — | -0.80 (1) | 0.96 | — |
| MDB | 27 | -0.43 [-0.76, -0.06] | — | -1.00 (1) | 0.90 | — |
| PSDB | 17 | +0.84 [+0.40, +1.27] | — | -1.00 (1) | 0.89 | — |
| PFL | 17 | +0.99 [+0.42, +1.39] | — | -1.00 (1) | 0.88 | — |

**Senado — 53ª legislatura (2007–2010)**: 149 votações, 0 temáticas, 93 linhas, variância explicada D1/D2 = 0.68/0.08, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 13 | -0.88 [-1.03, -0.69] | — | — | 0.97 | — |
| PTB | 9 | -0.50 [-0.93, +0.03] | — | — | 0.94 | — |
| MDB | 22 | -0.42 [-0.73, -0.16] | — | — | 0.88 | — |
| DEM | 15 | +1.19 [+0.88, +1.46] | — | — | 0.94 | — |
| PSDB | 14 | +1.40 [+1.12, +1.62] | — | — | 0.95 | — |

**Senado — 54ª legislatura (2011–2014)**: 159 votações, 2 temáticas, 99 linhas, variância explicada D1/D2 = 0.56/0.08, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 15 | -0.69 [-0.81, -0.57] | -1.00 (1) | +0.85 (1) | 0.93 | — |
| PL | 9 | -0.47 [-0.68, -0.22] | -1.00 (1) | +1.00 (1) | 0.88 | — |
| MDB | 23 | -0.31 [-0.54, -0.07] | -1.00 (1) | +0.85 (1) | 0.83 | — |
| PSDB | 12 | +1.95 [+1.64, +2.18] | -1.00 (1) | +1.00 (1) | 0.93 | — |

**Senado — 55ª legislatura (2015–2018)**: 94 votações, 1 temáticas, 87 linhas, variância explicada D1/D2 = 0.62/0.10, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 9 | -1.79 [-2.03, -1.44] | -1.00 (1) | — | 0.88 | — |
| MDB | 22 | +0.39 [-0.01, +0.66] | +0.60 (1) | — | 0.87 | — |
| PSDB | 12 | +0.71 [+0.39, +0.93] | +0.82 (1) | — | 0.92 | — |

**Senado — 56ª legislatura (2019–2022)**: 382 votações, 3 temáticas, 138 linhas, variância explicada D1/D2 = 0.40/0.17, orientação: thematic_anchor

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PODE | 13 | -0.24 [-0.86, +0.21] | +0.71 (3) | — | 0.79 | — |
| PSDB | 10 | -0.12 [-0.71, +0.39] | +0.33 (3) | — | 0.85 | — |
| MDB | 19 | +0.30 [+0.00, +0.67] | +0.28 (3) | — | 0.86 | — |
| UNIÃO | 9 | +0.36 [-0.09, +0.71] | -1.00 (1) | — | 0.84 | — |
| PSD | 15 | +0.55 [+0.24, +0.77] | +0.13 (3) | — | 0.89 | — |
| PP | 12 | +0.85 [+0.57, +1.15] | +0.44 (3) | — | 0.88 | — |
| PL | 9 | +0.87 [+0.58, +1.09] | +0.11 (1) | — | 0.89 | — |

**Senado — 57ª legislatura (2023–2026)**: 175 votações, 5 temáticas, 101 linhas, variância explicada D1/D2 = 0.56/0.11, orientação: member_continuity

| Partido | N | D1 [IC95%] | Econ | Soc | Rice | Gov.* |
|---|---|---|---|---|---|---|
| PT | 10 | -1.26 [-1.45, -1.04] | — | -0.46 (5) | 0.95 | — |
| MDB | 12 | -0.87 [-1.09, -0.65] | — | +0.64 (5) | 0.89 | — |
| PSD | 18 | -0.60 [-0.84, -0.29] | — | +0.69 (5) | 0.83 | — |
| PP | 8 | +0.83 [+0.41, +1.22] | — | +0.73 (5) | 0.86 | — |
| PL | 16 | +1.25 [+0.95, +1.49] | — | +0.67 (5) | 0.91 | — |

## 5. Como ler e limites

- **A dimensão 1 mistura ideologia e governo-oposição.** Nas legislaturas com orientação de governo disponível, a correlação entre D1 e a concordância com o governo é 0,99 na Câmara 56 e -0,81 na Câmara 57 (`first_dimension_vs_government_agreement`). Em 2003-2010 a maioria do plenário vota em bloco coalizão contra oposição; PL, PP, PTB e PMDB aparecem do lado do governo Lula na D1, o que mostra **coalizão e fisiologismo**, não esquerda. Nenhuma posição D1 de 2003-2014 deve ser lida como esquerda-direita sem outra evidência. O descritor de governo/oposição não entra em E/C (rubric, N1).
- **Escore temático é a medida mais direta e a mais escassa.** 28 votações no total; as legislaturas 51 e 53 não têm nenhuma na Câmara, nenhuma no Senado antes da 52. Onde há de 5 a 7 votações (Câmara 55 e 56) é utilizável; abaixo de 3, não.
- **Votação nominal não é amostra aleatória.** A Câmara 2003-2014 publica poucas votações nominais de texto principal por ano (6-24); votação simbólica não gera dado. O Senado tem 2015 e 2016 quase vazios (17 e 13 votações com votos, 5 e 2 de texto principal): lacuna da fonte, confirmada também no endpoint antigo.
- **Voto não é preferência.** Há disciplina de bancada, liderança, trocas de apoio por cargos e emendas, e votação estratégica (obstrução, retirada de pauta). Rice alto mede disciplina, não convicção. Obstrução e abstenção são tratadas como estado não direcional na PCA e reportadas à parte.
- **Ausência não é voto.** Parlamentar ausente não tem linha; "presente sem voto" e "Votou" (sigilo) são NaN. Taxas de ausência não foram usadas como sinal. Votação secreta do Senado fica fora.
- **Orientação de bancada.** O arquivo de orientações traz líderes por bloco (Governo, Oposição, Maioria, Minoria, partidos); só de 2020 em diante aparece "Governo". Antes disso o alinhamento ao governo não é calculado (lacuna, não zero). "Liberado" e "Obstrução" não são direções.
- **Rótulos de partido do Senado.** A fonte apresenta algumas siglas já atualizadas (MDB, CIDADANIA, AVANTE, REPUBLICANOS aparecem em anos em que o partido tinha outro nome), enquanto PFL/DEM permanecem históricas. Foram mantidas como publicadas, sem tentar corrigi-las. A comparação com a Câmara (que publica a sigla do momento: PMDB, PPS, PFL) exige cuidado.
- **Poucos parlamentares por partido.** O Senado tem 81 cadeiras; partidos com menos de 8 linhas não aparecem nas tabelas. Os dados completos mantêm partidos com 3 ou mais linhas e o campo `n_members`.
- **Seleção da votação por item.** Entre as votações de um mesmo item (turnos, emendas aglutinativas) escolhe-se a de maior participação. Em itens como maioridade penal essa votação pode ser a de uma emenda aglutinativa e não a do texto aprovado; a direção do "sim" permanece a do indicador.
- **Rubric ainda é proposta.** A direção dos itens depende do `rubric.json` em status `PROPOSTA_PARA_APROVACAO`; mudar um polo exige reexecutar `build_party_vote_positions.py`.
- **Sem dados 1991-2000 na Câmara** (votos nominais não publicados) e 1991-2002 do Senado muito esparsos (de 1 a 64 votações de texto principal por ano).
- **Sem causalidade nem rótulos.** Nenhum partido é classificado aqui como esquerda, centro, direita ou extremo. As saídas são insumos de comportamento para o modelo, a serem combinadas com as demais evidências do rubric.

## 6. Custo

Seja N o número de votos individuais. Leitura e normalização: O(N) em streaming, memória O(votações de um ano). Agregação por partido: O(N). PCA: O(L·C·min(L,C)) por ajuste (L linhas, C votações, 8 iterações EM) vezes as réplicas; a matriz é densa (L até ~800, C até ~250). Não há N+1 remoto nem varredura repetida dos arquivos brutos.
