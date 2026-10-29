# Reconciliação do inventário do Senado (1992–1994) com o banco

Referência: 28/10/2026. Janela: 02/10/1992 a 01/01/1995. Acesso ao PostgreSQL somente leitura (transação `READ ONLY`, consultas em lote, sem gravação e sem credenciais em arquivos). Consultas: `db/queries/senate_itamar_1992_1994_reconciliation.sql`. Extrações com manifesto e SHA-256: `data/political-dashboard/senate-itamar-db-snapshot-20261028/` (ignorado pelo git). Resultado por cadeira e data: `data/political-dashboard/senate-itamar-db-reconciliation-20261028.json`.

## Conclusão

O banco **não cobre** o governo Itamar no Senado. Ele não confirma nem contradiz nenhuma das 243 linhas cadeira-data (81 × 3), e não resolve nenhum dos partidos "não identificados" (7, 13 e 15). O inventário continua sendo a única fonte do período.

| Item | Resultado |
|---|---|
| Ocupantes distintos nas três fotografias | 91 |
| Com `person_identifier` (senado/senator) | 1 (Esperidião Amin, ID 22): 1,1% |
| Com `office_exercise`/`office_term` na janela | 0 (mandato de senador mais antigo no banco: 01/02/2019) |
| Com filiação datada na janela | 0 |
| Declarações eleitorais TSE de 1990 e 1994 | 0 (candidaturas começam em 2004; bens em 2018, 2022 e 2026) |
| Votações nominais anteriores a 2026 | 0 (a mais antiga é 14/10/2026) |
| "Partido não identificado" resolvidos pelo banco | 0 de 7, 0 de 13, 0 de 15 |

O banco guarda 81 identificadores do Senado, todos de senadores atuais (2019 em diante); apenas Amin coincide com o inventário.

## Por cadeira

- 80 cadeiras por data: pessoa ausente do banco. Status `not_in_database`; ocupante e partido do inventário permanecem sem corroboração.
- SC, Esperidião Amin: o banco tem a pessoa (UUID `cb9d7d8c-…`) e três filiações a PP sem intervalo (TSE 2018, TSE 2026 e `institution:senado`, fonte `https://legis.senado.leg.br/dadosabertos/senador/22.json`, registros 261762/268911/270294). Elas apenas "tocam" a janela porque `valid_from` e `valid_until` são nulos. O inventário diz PDS (1992) e PPR (1993, 1994) pelo intervalo da API. Não é contradição, pois filiação posterior não prova a anterior. Status `in_database_without_dated_evidence`. O mandato de 1991–1996 não está no banco.

## Partidos não identificados

Nenhum é resolvido pelo banco, pois nenhum dos ocupantes tem filiação datada.

- 1992 (7): Alfredo Campos (MG, 1383), Juvêncio Dias (PA, 136), Mansueto de Lavor (PE, 2194), Álvaro Pacheco (PI, 1398), José Richa (PR, 1974), Dario Pereira (RN, 1572), Eva Blay (SP, 1618).
- 1993 (13): Carlos De' Carli (AM, 1537), Henrique Almeida (AP, 1737), Pedro Teixeira (DF, 2190), Meira Filho (DF, 1781), Gerson Camata (ES, 28), Irapuan Costa Júnior (GO, 1749), Alexandre Costa (MA, 2), Jarbas Passarinho (PA, 1764), Mansueto de Lavor, José Richa, Dario Pereira, Eva Blay, Moisés Abrão (TO, 2131).
- 1994 (15): Carlos De' Carli, Meira Filho, João Calmon (ES, 1799), Alexandre Costa, Alfredo Campos, Saldanha Derzi (MS, 2203), Louremberg Nunes (MT, 2017), Almir Gabriel (PA, 1387), Jarbas Passarinho, José Richa, Nelson Carneiro (RJ, 2137), Hydekel Freitas (RJ, 1746), Paulo Bisol (RS, 1967), Francisco Rollemberg (SE, 1687), Fernando Henrique Cardoso (SP, 1634).

## Conflitos

Todos permanecem como no inventário, porque nenhum dos envolvidos está no banco: Ney Suassuna (PTB-PB em cabeçalho de 11/03/1993 × MDB na API), Lavoisier Maia (S/Partido na API × lista impressa), Júnia Marise (lista impressa × API), Carlos De' Carli (1537) × Carlos de Carli (1542), a cadeira de Henrique Almeida (AP) em 1994 e os retornos prováveis sem ato de Alexandre Costa (MA), Hugo Napoleão (PI), José Eduardo (PR) e Fernando Henrique Cardoso (SP). Sem dado novo, nenhuma escolha foi feita. Os IDs 1537 e 1542 ficam como identidades separadas, e não houve junção por nome.

## Catálogo de partidos

`political_party` tem 38 registros, todos atuais (AGIR, AVANTE, CIDADANIA, DC, DEMOCRATA, MDB, MISSÃO, MOBILIZA, NOVO, PAN, PATRIOTA, PCB, PCdoB, PCO, PDT, PHS, PL, PODE com códigos 19 e 20, PP, PPL, PRD, PRONA, PROS, PRTB, PSB, PSD, PSDB, PSL, PSOL, PSTU, PT, PV, REDE, REPUBLICANOS, SOLIDARIEDADE, UNIÃO, UP). Faltam os partidos históricos PFL, PRN, PDS, PPR, PTB, PDC, PTR e o PSD de 1992, que o banco não registra. Códigos coincidentes não provam identidade. PL/22, PP/11, DC/27 e MDB/15 são partidos de épocas diferentes dos homônimos de 1992–1994 (PL de 1992, PP de 1993, PDC e PMDB). Associar um ao outro exige ato de sucessão com fonte e data, nunca igualdade de sigla.

## O que falta ingerir (não executado)

1. API de dados abertos do Senado, para os 90 IDs restantes: `/senador/{id}` (pessoa e identificador), `/senador/{id}/mandatos` (mandatos e exercícios titular/suplente das legislaturas 48–49) e `/senador/{id}/filiacoes` (intervalos). Isso preenche pessoa, `office_term`, `office_exercise` e `political_party_affiliation` no escopo `institution:senado:historical_affiliations`, com `source_record` e URL.
2. `political_party` históricos (PFL, PRN, PDS, PPR, PTB, PDC, PTR, PSD, PL, PP e demais) com códigos duráveis distintos dos atuais e relações de sucessão datadas.
3. Votações nominais de 1992–1994 (cabeçalho partidário do voto, `person_vote.political_party_observed`), no lote que já alimenta o inventário (9 votações em 1992).
4. TSE: candidaturas e bens das eleições de 1990 e 1994 (repositório de dados abertos do TSE; o banco só carrega 2004 em diante). Para os 54 senadores eleitos em 1990 e os de 1994, isso dá o partido na eleição, com escopo `electoral:1990`/`electoral:1994`. A cobertura de 1990 no TSE é parcial, e a ausência não prova nada.
5. Atos de licença, convocação e posse (Diário do Congresso e Diário Oficial) para os retornos sem ato e a cadeira de Henrique Almeida; a API de licenças não devolve esse período.
6. Resolução de identidade 1537 × 1542 via `person_identity_review`, sem junção por nome.

## Integração futura

Nenhuma cadeira ou partido do inventário pode ser alterado com base no banco hoje. Os arquivos `senate_orientation_1992_1994.*`, `data/political-orientation/*` e `docs/partidos-*` não foram tocados. Após a ingestão acima, reexecutar as consultas e comparar por `senate_person_id` e data.
