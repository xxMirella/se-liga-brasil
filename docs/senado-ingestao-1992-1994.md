# Ingestão do Senado de 1992–1994 no banco

Referência: 28/10/2026. Recorte: 02/10/1992 a 01/01/1995, fim exclusivo (a fonte publica o último dia inclusivo; o banco guarda o dia seguinte). Estado: **código, SQL, testes e simulação (dry-run) prontos; nada foi gravado no banco real.** A gravação (`--apply`) é decisão explícita da usuária.

## 1. Como o projeto ingere o Senado hoje

| Caminho | O que faz | Observação |
|---|---|---|
| `src/crawlers/senado/pipeline.py` + `staging.py` + `institutional_projection.py` | Lista atual (`senador/lista/atual.json`) e perfil (`senador/{id}.json`) viram registros validados, versionados em `ingestion_entity*`, projetados por `db/ingestion/senado_profile.sql` e `person_current_public_office.sql` | Só senadores **em exercício hoje**. Identidade: `personal_identities.sql` + `senado_institutional_identity.sql` gravam `person_identifier(source=senado, namespace=senator, external_id=<ID oficial>)` |
| `db/ingestion/senado_profile.sql` | `political_party_affiliation` (escopo `institution:senado`), `office_term`, `office_exercise`, `person_fact` | Casa o partido **pela sigla** (`GROUP BY abbreviation HAVING count(*)=1`); chave do mandato `"<person_id>:<legislatura1>-<legislatura2>"` |
| `src/database/senate_affiliation_history.py` + `scripts/persist_senate_affiliation_history.py` | Histórico de filiações de **uma** pessoa (Flávio Bolsonaro, ID 5894, fonte relacional 311675, escopo `institution:senado:historical_affiliations`) | Resolve a pessoa só pelo ID oficial, exige partido único por sigla, **recusa retorno ao mesmo partido** (`REPEATED_POLITICAL_PARTY_REQUIRES_PER_INTERVAL_SOURCE_RECORDS`), registra `S/Partido` em `person_fact` (`senate_no_affiliation_intervals`), guarda o corpo original como `source_record` (SHA-256, `storage_reference`) |
| `src/service/senate_history/` | Calendário, composições anuais, rosters; leitura, não gravação | Alimenta os painéis, não o banco |

Tabelas envolvidas e constraints relevantes (conferidas no schema real e em `db/schema.sql` + migrações):

- `source_record`: `UNIQUE(source_id, external_key, content_sha256)`. É o hash/arquivamento da fonte: mesma chave + mesmo conteúdo = mesmo registro; conteúdo novo = novo registro (histórico preservado).
- `person_identifier`: PK `(source_id, namespace, external_id)`. É a ponte oficial; nunca nome.
- `political_party`: `code UNIQUE`; `abbreviation` **não** é única.
- `political_party_affiliation`: `UNIQUE(person_id, political_party_id, source_record_id)`, `valid_until > valid_from`, `evidence_kind in (administrative, electoral_declaration, official_membership)`. Por isso o retorno ao mesmo partido só cabe com **um `source_record` por intervalo**.
- `office_term`: `UNIQUE(institution_id, official_term_key)`; `office_exercise`: `UNIQUE(term_id, starts_on)`, `capacity in (holder, substitute)`.
- `person_profile` (visão materializada): derivada; precisa de `REFRESH` depois da gravação.

## 2. O que a carga faz

Comando (padrão = simulação):

```sh
.venv/bin/se-liga-brasil load-senate-history-1992-1994 --env-file /home/mirella/projetos/mdqc-knowledge-center/.env
```

Fluxo (todos os módulos são Python 3.12, uma responsabilidade por arquivo):

1. `crawlers/senado/historical_period_archive.py` lê as respostas arquivadas e **confere o SHA-256 de cada arquivo** contra o manifesto (`data/political-dashboard/senate-history-1992-1994-source/manifest.json`, entradas mais novas; `itamar-senate-sources/source-integrity-manifest.json` como complemento). Arquivo ausente ou com hash divergente vira pendência, nunca dado.
2. `historical_period_normalization.py` normaliza identidade (`/senador/{id}`), mandatos e exercícios (`/mandatos`), filiações (`/filiacoes`) e o catálogo de partidos (`/senador/partidos`). O ID dentro de cada documento tem de ser igual ao ID pedido (`SENATOR_SOURCE_ID_MISMATCH`).
3. `historical_period_validation.py` + `historical_period_plan.py` aplicam as regras: janela semiaberta, intervalos sem sobreposição (um intervalo aberto seguido de outro também é recusado), exercício dentro do mandato, nascimento obrigatório para criar pessoa. Escopo = os 96 IDs do inventário `itamar-senate-inventory-1992-1994.json`.
4. `historical_period_withheld.py` retira o que a revisão documental não resolveu (seção 5).
5. `service/ingestion/historical_load.py` é o executor genérico (sem regra do Senado): grava o plano **duas vezes na mesma transação**; a segunda passagem tem de inserir 0 em todas as tabelas.
6. `database/historical_senate_load.py` + `db/ingestion/senado_historical_period.sql` gravam em lote, um comando por tabela (sem N+1), todos idempotentes e devolvendo as linhas realmente inseridas.
7. `crawlers/senado/historical_period_report.py` produz o relatório JSON.

### Mapeamento fonte → banco

| Fonte (API do Senado) | Tabela | Regra |
|---|---|---|
| Arquivos baixados (detalhe, mandatos, filiações, catálogo) | `source_record` | `external_key = senate_history_1992_1994:senator:{id}:{detail|mandates|affiliations}`; `content_sha256` = SHA-256 dos bytes originais; `storage_reference` = caminho arquivado. O detalhe guarda só identificação e nascimento (e-mail e contatos não são copiados). |
| Um intervalo de filiação | `source_record` próprio | chave `...:affiliation:{código Senado do partido}:{início}`; hash do próprio elemento. Permite retorno ao mesmo partido sem violar a constraint. |
| `/senador/{id}` | `person` + `person_identifier(senado, senator, id)` + `person_fact senate_history_1992_1994:official_senator_identity` | UUID derivado do ID oficial (`uuid5`), então reexecutar nunca cria outra pessoa. |
| `/mandatos` | `office_term` | `office_kind=senator`, chave `"<person_id>:<leg1>-<leg2>"` (mesma convenção da lista atual), início da 1ª legislatura, fim exclusivo = fim da 2ª + 1 dia. Mandato repetido sem código/participação é o mesmo mandato. |
| `/mandatos` → `Exercicios` | `office_exercise` | `holder` para Titular, `substitute` para suplente; fim inclusivo + 1 dia. **Só o que a API publica**: mandato sem exercício informado não gera exercício. |
| `/filiacoes` | `political_party_affiliation` | escopo `institution:senado:historical_affiliations`, `evidence_kind=administrative`, `valid_from`/`valid_until` do intervalo (fim exclusivo), `observed_on = valid_from`, `information_valid_from = momento do download`. |
| `S/Partido` (código 163) | `person_fact senate_no_affiliation_intervals` | nunca vira partido. |
| Filiação só com ano (`AnoFiliacao`) | `person_fact senate_affiliation_year_precision_claims` (`review_status=incomplete`) | nenhum dia é inventado. |
| `/senador/partidos` | `political_party` | veja abaixo. |

### Partidos históricos

- `code = senado:party:{Codigo do catálogo do Senado}`; nunca o número do TSE. Isso separa, por exemplo, PL/25 (1985–2006) do PL atual, PSD/89 (1987–2003) do PSD atual e MDB/33 do MDB/15 do TSE. Código ou sigla iguais não provam identidade.
- `abbreviation = sigla publicada` (PFL, PRN, PDS, PPR, PDC, PTB). Se outra linha de `political_party` já usa a mesma sigla, a abreviação recebe o período do catálogo (`MDB (1980-)`, `PP (1993-1995)`). Motivo: `senado_profile.sql`, `camara_profile.sql`, `alerj_profile.sql` e a busca pública casam partido **pela sigla** e exigem unicidade; uma segunda linha `MDB` quebraria a ingestão atual dos senadores (o mesmo problema dos códigos 19/20 do Podemos).
- Partido sem código nem sigla na fonte (ex.: "Partido Democrático Universitário da Bahia", Nelson Carneiro, ID 2137, sem datas) não é criado.
- **Sucessão entre partidos não foi gravada.** Não há tabela de sucessão no schema e as fontes arquivadas (CPDOC/DHBB, em `data/political-orientation/party-sources-1992-1994/`) só dão o mês: PTR + PST → PP em fevereiro de 1993; PDS + PDC → PPR em abril de 1993 ("Consumada em abril de 1993, a fusão resultou no PPR"); PP + PPR → PPB em setembro de 1995 (fora do recorte). O catálogo do Senado extingue PDS e PDC em 16/06/1993 e cria PPR em 01/04/1993; a diferença entre as duas datas oficiais é uma divergência a resolver, não a escolher. Gravar a sucessão exige uma tabela nova (migração) e uma data exata com fonte.

## 3. Resultado da simulação no banco real (28/10/2026)

Relatório: `data/political-dashboard/senate-history-1992-1994-dry-run-report-20261028.json`. A transação foi sempre revertida (pessoas 15.921, partidos 38 e registros `senate_history_1992_1994:*` = 0 depois). Segunda passagem: 0 inserções em todas as tabelas.

| Tabela | Inseriria |
|---|---|
| `person` | 84 |
| `person_identifier` | 84 |
| `office_term` | 88 |
| `office_exercise` | 26 |
| `political_party` | 11 (PDT, PFL, MDB, PP, PPR, PSB, PSDB, PTB, PRN, PDC, PDS) |
| `political_party_affiliation` | 70 |
| `person_fact` | 103 |
| `source_record` | 342 |
| `source`, `institution` | 0 |

Oitenta e seis senadores entram no plano; 85 são gravados (84 pessoas novas e 1, Esperidião Amin, ID 22, reaproveitado pelo identificador oficial que já existe) e 1 aguarda revisão. Outros 53 IDs da lista oficial da 49ª legislatura não estão no inventário de ocupantes verificados e não foram tratados como tal (lista no relatório).

## 4. Identidade

1. Se `person_identifier(senado, senator, ID)` existe, a pessoa é essa (e não pode ser alias de fusão).
2. Se não existe, procura-se pessoa **com o mesmo nome civil normalizado e a mesma data de nascimento** (a regra já usada por `personal_identities.sql`). Qualquer coincidência **não é ligada automaticamente**: vira `IDENTITY_REVIEW_REQUIRED` e o senador fica fora da carga. Hoje há um caso: ID 17, Eduardo Suplicy, coincide com a pessoa `31f09c91-08e6-48e3-9ae6-b8481d07d977` (candidaturas TSE 2006–2026, sem ID do Senado).
3. Para aprovar, a usuária passa `--reviewed-identities arquivo.json` com `{"senado_links": [{"senator_id": "17", "person_id": "<uuid>"}]}`. A aprovação só vale se o UUID for exatamente o que a consulta por nome+nascimento devolve.
4. Sem coincidência, cria-se a pessoa nova. A checagem só enxerga pessoas com `normalized_name` preenchido; homônimos sem esse campo não seriam detectados.
5. Os IDs 1537 (Carlos De' Carli) e 1542 (Carlos de Carli) ficam fora; a unificação, se for o caso, passa por `person_identity_review`.

## 5. Pendências: não ingeridas como fato

Todas estão em `pending` do relatório, com ID e motivo.

- **Fora por completo:** 1537 e 1542 (identidade).
- **Sem filiações:** Ney Suassuna (63, PTB do cabeçalho de 11/03/1993 × MDB na API; sem mandato com exercício na janela, portanto também não entra), Lavoisier Maia (799) e Júnia Marise (51), cujas listas impressas divergem da API.
- **Sem exercícios:** Henrique Almeida (1737, cadeira do AP em 1994) e os "retornos prováveis sem ato" de Alexandre Costa (2), Hugo Napoleão (32), José Eduardo (85) e Fernando Henrique Cardoso (1634). Para o ID 85, 1 exercício que a API publica foi retido; os demais não tinham exercício na API. Retirar o bloqueio exige ato datado.
- **Sem mandato na janela com exercício comprovado (8):** 56, 63, 136, 139, 161, 1503, 1746, 2144 (suplentes sem exercício informado na janela). Doze mandatos de suplente sem exercício foram deixados de fora (`SUBSTITUTE_TERM_WITHOUT_EXERCISE`).
- **Mandato carregado sem saber se titular ou suplente (13):** a API do Senado não publica a participação de mandatos antigos (legislaturas 48–49 sem `CodigoMandato`). O `office_term` é gravado (existe mandato), mas nenhum `office_exercise` (a capacidade é obrigatória). IDs: 185, 1025, 1398, 1552, 1572, 1618 (Eva Blay), 1737, 1869, 2017, 2190, 2937, 3233, 3272.
- **Partido não identificado:** 1 registro (ID 2137). Os "partidos não identificados" das fotografias 1992/1993/1994 (Alfredo Campos, Juvêncio Dias, Mansueto de Lavor etc.) continuam sem partido onde a API não traz filiação datada; nenhum partido foi inferido.
- **Filiações só com ano:** 21 registros ficam como `person_fact` incompleto, sem datas.
- **Intervalos sobrepostos:** nenhum senador do recorte tem sobreposição; se a API ou um novo download trouxer uma, só as filiações daquele senador são retidas (`OVERLAPPING_INTERVALS`).
- **Licenças e afastamentos** (`/licencas`): baixadas, mas não gravadas; exercício é o que a API publica em `Exercicios`, sem subtrair licenças.
- Votações nominais, candidaturas e bens do TSE de 1990/1994 e a sucessão de partidos continuam fora (seção 2).

## 6. Riscos

1. **Cartão "partido atual" de pessoas históricas.** 16 senadores têm a última filiação sem data de fim na API (IDs 17, 47, 62, 68, 88, 1025, 1562, 1579, 1657, 1864, 1869, 1952, 2139, 2224, 2937, 3272). `person_profile` trata fim nulo como vigente, então o cartão mostrará esse partido como "último observado". A fonte é a do Senado; a ausência de fim não prova filiação em 2026. Para não superar observações mais novas de pessoas já existentes, `observed_on` é o início do intervalo, não a data do download.
2. **Novas pessoas em `person_profile` e na busca por nome.** A busca pública não filtra por exercício atual: depois de `REFRESH`, 84 pessoas históricas aparecem. O `--apply` executa o `REFRESH` depois do commit.
3. **Sigla duplicada.** Se um dia a TSE/Câmara criar uma linha com a sigla de um partido histórico não qualificado (PFL, PRN, PDS, PPR, PDC, PTB), a ingestão atual do Senado por sigla ficará ambígua para essa sigla. Hoje não há colisão.
4. **Identidade só por nome+nascimento** (item 4 da seção 4) pode não detectar quem não tem `normalized_name`.
5. **Mandatos sem participação** (13) afirmam apenas a existência do mandato.
6. Sequências `GENERATED ALWAYS AS IDENTITY` avançam mesmo na simulação (lacunas de ID, sem efeito sobre os dados).
7. Os dados vêm de respostas de 28/10/2026 já arquivadas por hash; se a API mudar, uma nova rodada gera novos `source_record` (histórico preservado), sem sobrescrever.

## 7. Como rodar

Simulação (padrão, sempre reverte, mostra contagens e prova idempotência; relatório em `data/political-dashboard/`):

```sh
.venv/bin/se-liga-brasil load-senate-history-1992-1994 --env-file /home/mirella/projetos/mdqc-knowledge-center/.env
```

Gravação (**só com decisão explícita**):

```sh
.venv/bin/se-liga-brasil load-senate-history-1992-1994 --apply --env-file /home/mirella/projetos/mdqc-knowledge-center/.env [--reviewed-identities arquivo.json]
```

Garantias no código (`service/ingestion/historical_load.py`):

- Dry-run usa `transaction(force_rollback=True)`: a transação é revertida mesmo sem erro e também em qualquer exceção. O executor recusa conexões que não estejam ociosas em autocommit, onde o "rollback" seria apenas um savepoint.
- `--apply` grava na mesma transação, repete a gravação e exige 0 inserções na segunda passagem; qualquer linha existente que discorde (mandato com UF/datas diferentes, exercício, filiação) aborta tudo (`EXISTING_ROWS_CONFLICT_WITH_LOAD`).
- Lock consultivo `pg_advisory_xact_lock` impede duas cargas simultâneas; `lock_timeout` 10 s e `statement_timeout` 120 s.
- Credenciais nunca vão a relatório ou log.

Depois do `--apply`, conferir com `db/queries/senate_history_1992_1994_verification.sql` (contagens, histórico por pessoa, ID duplicado, sobreposição).

## 8. Plano de rollback

`db/repairs/senate_history_1992_1994_rollback.sql` (termina em `ROLLBACK`; troque por `COMMIT` depois de ver as contagens, e rode `REFRESH MATERIALIZED VIEW se_liga_brasil.person_profile`). Remove apenas linhas cujo `source_record` tem a chave `senate_history_1992_1994:*`. Pessoas criadas pela carga só são apagadas se nada mais as referenciar: as chaves estrangeiras abortam a transação se houver dado posterior. Pessoas que já existiam (Amin) mantêm suas linhas, perdendo só o que a carga acrescentou. Testado em PostgreSQL descartável (apaga exatamente o que a carga inseriu; aborta se houver dependência).

## 9. Testes

- `tests/test_senate_history_load_1992_1994.py` (23): fim inclusivo → exclusivo, janela semiaberta, sobreposição e intervalo aberto recusados, ID oficial obrigatório e conferido, hash adulterado, partido sem código ou fora do catálogo, `S/Partido`, filiação só com ano, retenções documentais, mandatos repetidos, exercícios inválidos, nascimento obrigatório, UUID derivado do ID, e o executor (dry-run reverte, apply só confirma depois da segunda passagem sem inserções).
- `tests/test_senate_history_load_integration.py` (12): SQL real em schema temporário que é sempre removido (`TEST_DATABASE_URL` ou `SE_LIGA_BRASIL_TEST_ENV_FILE`; sem eles os testes são ignorados): contagens, nada deixado pelo dry-run nem por erro no meio, retorno ao mesmo partido (PFL → PRN → PFL), `S/Partido` sem partido, fins exclusivos, colisão de sigla, identidade existente, revisão de nome+nascimento, conflito que aborta o apply, e o script de rollback.
- Fixtures com pessoas fictícias ficam só em `tmp_path` e em schemas descartáveis; nenhum teste usa o banco de produção.
