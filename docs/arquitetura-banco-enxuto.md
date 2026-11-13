# Arquitetura de banco enxuto: só o que o site lê vai para o Supabase

Status: proposta para decisão (12/11/2026). Nenhum código, migration ou dado foi alterado. Medidas de banco vêm do relatório de auditoria de 12/11/2026 (somente leitura); estimativas novas estão marcadas como "estimativa" e devem ser confirmadas por piloto antes de cada etapa.

## 0. Decisão em uma página

- Problema: `pg_database_size` = 1340 MB contra 500 MB do plano gratuito. 806 MB são camada de ingestão (`source_record`, `ingestion_entity`, `ingestion_entity_version`, `ingestion_artifact_entity`), com o mesmo JSON normalizado gravado três vezes. Mesmo aplicando todas as ações seguras da auditoria o banco fica em 700 a 860 MB.
- Decisão recomendada: o **Postgres canônico completo passa a ser local** (PostgreSQL 17 na máquina da usuária, mesmo esquema `se_liga_brasil`, mesmas migrations e SQL de `db/ingestion/`). O **Supabase passa a guardar somente o schema `se_liga_brasil_serving`** (datasets de leitura, já existente) e o Storage guarda histórico compacto em Parquet e backups.
- Resultado esperado no Supabase: cerca de 175 MB em regime (68 MB de sistema e do schema `knowledge`, mais cerca de 107 MB de datasets), pico de cerca de 215 MB durante o build. Mesmo com os datasets 50 % maiores que a estimativa, o pico fica em cerca de 270 MB. Meta: < 400 MB com margem de pelo menos 130 MB.
- Por que não manter um núcleo canônico no Supabase: o menor conjunto que o site precisa ler ao vivo soma cerca de 285 MB (seção 2.4). Com serving e sistema chega a cerca de 460 MB. Não cabe em 400 MB.
- O que muda no código é pequeno e já tem ponto de apoio: o construtor atômico (`src/service/serving/builder.py`) passa a ler de uma conexão (local) e escrever em outra (Supabase); faltam datasets para cobrir todas as páginas; o leitor público passa a não ter fallback canônico.

## 1. Inventário: o que o site lê hoje

Transporte: `src/application/public_portal.py` (roteamento) e `src/application/vercel.py` (WSGI na Vercel). Leituras de banco usam `PublicReadConnectionPool` (`src/database/public_read_connections.py`, porta 6543) com a mesma `DATABASE_URL` dos crawlers (`:47` e `src/database/operations.py:17`). Não existe papel de leitura separado (`db/migrations/0023_serving_schema.sql:3-4`).

| Rota | Código | Lê do Postgres hoje | Já fora do banco ou em serving |
| --- | --- | --- | --- |
| `/`, `/sobre`, `/como-funciona`, `/fontes-dos-dados`, `/comparacao-de-classificacoes`, `/assets/*`, fontes | `public_portal.py:211-245` | Nada | Páginas geradas em Python/arquivos estáticos |
| `/pessoas`, `/api/people` (busca, ordenação por nome, partido, UF) | `people_search.py`, `public_people_directory.py:35-47`, fallback `public_people.py:44` | Serving `person_directory` se a release tem menos de 1 dia; senão `person`, `person_identity_alias`, `office_term`, `office_exercise`, `political_party_affiliation`, `political_party` | `person_directory` (`serving/person_directory.py`, 7 índices) |
| Lista de partidos da busca | `political_party_options.py`, `public_people.py:80` | Idem (diretório `parties_current` ou canônico) | `person_directory` |
| `/pessoas/{id}`, `/api/people/{id}` (perfil, aba Perfil) | `person_profile_loader.py`, `person_profile_reads.py:14-28` (13 leituras) | Snapshot se existir; senão ao vivo: `person`, `institution`, `office_term`, `office_exercise`, `source_record` (`fetched_at`, `source_url`, `payload->>'documentUrl'`), `person_fact` verificados (`camara_attendance:`, `alesp_attendance:`, `alerj_historical_activity:`, `senado_cabinet_payroll:`, `current_public_office_observation`), `political_party_affiliation`, `person_payroll_payment`, `candidate_asset_declaration`, `electoral_candidacy`, `office_legal_scope_version`, `proposition`, `proposition_person`, `proposition_event`, `ingestion_entity` (só `camara_legislative_detail`, `public_propositions.py:32`) | `person_profile_snapshot` só para ~290 a 700 pessoas (`SCOPE_SQL`, `person_profile_snapshot.py:34-45`); proposições: só a página 1 |
| Perfil, aba Atividade e `/api/people/{id}/votes` (votos individuais, histórico) | `person_votes.py`, `storage_votes.py:57-65`, `storage_history.py` | Só metadados: `person`, `office_exercise`, `office_term`, `institution`, `person_career_coverage_receipt` (`public_profile.py:41,105`) | **Votos em Parquet no Storage** (bucket privado `voting-datasets`, `dataset_storage/supabase.py`, catálogo em `catalog.py`, cache em disco `read.py`) |
| `/panorama` | `majority_panorama_reader.py:100-125` | Serving `majority_panorama_document` (1 linha); sem release, monta ao vivo (~11 leituras do painel) a partir de `political_dashboard_annual` | `majority_panorama_document` |
| `/api/political-dashboard` | `political_dashboard_reader.py`, `political_dashboard_analytical.py:150-220`, `political_dashboard_history.py:35-51` | `political_dashboard_annual` (partições do ano), `political_dashboard_history` (um registro compactado por território), `political_dashboard_territory_catalog` (`political_dashboard_analytical.py:300`) | Nenhum (são tabelas de leitura já pré-calculadas, só no schema errado) |
| `/sitemap.xml`, `/sitemaps/people-XX.xml` | `search_indexing.py` (app), `database/search_indexing.py:25,32` | `person` (ids públicos) | Pode sair do `person_directory` |

Conclusões do inventário:

1. O Parquet de votos já está fora do banco. O Parquet local do repositório analítico (`docs/repositorio-analitico-local.md`) não é lido pelo site: "a aplicação pública não abre Parquet por visita".
2. Três das sete superfícies já têm dataset serving, mas todas mantêm fallback que lê as tabelas canônicas. É por esse fallback que o Supabase ainda precisa do canônico inteiro.
3. O site **nunca lê** `ingestion_entity_version`, `ingestion_artifact_entity`, `person_activity_context`, `person_data_gap` e os 110 mil fatos `tse:*` pendentes de `person_fact` (leitura pública sempre filtra `review_status='verified'` e prefixos específicos; `crawlers/tse/requested_data.py:98` lê `tse:candidate:` só no pipeline). `ingestion_entity` só é lida publicamente numa linha de tipo (`public_propositions.py:32`) e, no pipeline, por `record_lookup.py:26` (existência por chave).
4. `source_record` é lida pelo site só por 3 colunas (`fetched_at`, `source_url`, e `payload->>'documentUrl'` dos eventos de proposição, `public_propositions.py:24-25`), mas é alvo de FK de cerca de 20 tabelas.

## 2. Arquitetura-alvo

### 2.1 Camadas

| Camada | Onde | Conteúdo | Quem lê |
| --- | --- | --- | --- |
| (a) Núcleo canônico completo | **PostgreSQL local**, schema `se_liga_brasil` (hoje 1272 MB; sem limite prático) | Todas as tabelas atuais, com constraints, versões e proveniência | Pipelines e construtores de dataset; nunca o site |
| (b) Datasets de leitura | **Supabase**, schema `se_liga_brasil_serving` | Dados já derivados, sem payload bruto | Site (Vercel) |
| (c) Ingestão e brutos | **Disco local** `data/` (22 GB: `tse` 17 GB, `political-orientation` 3,4 GB, `alesp` 529 MB etc.), NDJSON de staging, quarentena | Arquivos originais imutáveis por SHA-256, staging validado | Pipelines |
| (d) Histórico e backup | `data/archive/` (Parquet) + **Supabase Storage** (1 GB grátis, separado dos 500 MB do banco) | Exportações Parquet das tabelas de versão/artefato, dumps criptografados do canônico | Auditoria e restauração |

A camada (a) local não precisa de otimização de espaço. A otimização é eliminar o que o site não lê do Supabase, e não alterar o modelo canônico.

### 2.2 Destino de cada tabela (nomes e MB do relatório)

Soma das linhas: 1267 MB (o relatório informa 1250 por arredondamento das 15 maiores; o schema mede 1272).

| Tabela | MB hoje | Destino | No Supabase depois |
| --- | --- | --- | --- |
| `source_record` | 315,2 | Fica no canônico local (FK de ~20 tabelas, proveniência). Site lê só `fetched_at`/`source_url`/`documentUrl`: esses campos entram nos datasets | 0 |
| `ingestion_entity` | 237,6 | Local. Reconciliação por chave+hash continua (seção 3). Detalhe da Câmara que o site usa (`principalProposition`, `textUrl`) vai para `person_proposition_page` | 0 |
| `ingestion_entity_version` | 209,6 | Local + export Parquet mensal (histórico). Nunca lida em `src/` | 0 |
| `person_fact` | 131,4 | Local. Fatos verificados que o site usa (assiduidade, folha de gabinete, atividade ALERJ, observação de cargo) entram em `person_profile_snapshot`. Os 110 mil `tse:*` pendentes: local + Parquet | 0 |
| `person_data_gap` | 92,2 | Local (fila de trabalho do pipeline; 4,45 M de updates sobre 112 mil linhas, `claim_data_gaps.sql`) | 0 |
| `proposition` | 60,9 | Local; vira `person_proposition_page` (serving) | 0 |
| `ingestion_artifact_entity` | 43,8 | Local + Parquet. Sem leitura em `src/` | 0 |
| `proposition_person` | 39,7 | Local; vira `person_proposition_page` | 0 |
| `person_activity_context` | 38,3 | Local + Parquet. Só INSERT em `activity_context.py` | 0 |
| `political_dashboard_annual` | 26,1 | Local (escrita por `activate_partitions`) e cópia em serving como `political_dashboard_partition` | 26 |
| `electoral_candidacy` | 17,5 | Local; escopo legal entra no snapshot do perfil | 0 |
| `political_party_affiliation` | 15,5 | Local; entra em `person_directory` e snapshot | 0 |
| `candidate_asset_declaration` | 15,1 | Local; entra no snapshot (13 leituras, `fetch_asset_*`) | 0 |
| `person` | 13,6 | Local; entra em `person_directory` e snapshot | 0 |
| `person_identifier` | 5,8 | Local | 0 |
| `person_document_identity` | 4,7 | Local. Hash de documento pessoal nunca deve sair da máquina | 0 |
| 30 demais tabelas (< 1,5 cada, ~5 MB) | ~5 | Local. Cópias necessárias ao site: `person_career_coverage_receipt` e `office_exercise` (via `person_vote_context`), `political_dashboard_history` e `political_dashboard_territory_catalog` (serving), `office_legal_scope_version` (dentro do snapshot) | ~1 |
| Tabelas vazias (`amendment_*`, `budget_amendment`, `business*`, `education`, `law`, `proposition_law`, `candidate_document`, `public_career_event`) | 0 | Local, sem ação | 0 |

Ao fim, nenhuma tabela canônica permanece no Supabase.

### 2.3 Datasets em `se_liga_brasil_serving` e orçamento

Existentes (`src/service/serving/registry.py:17-21`): `person_directory`, `person_profile_snapshot`, `majority_panorama_document`, `dataset_release`. Novos ou ampliados:

| Dataset | Chave | Conteúdo | Estimativa MB |
| --- | --- | --- | --- |
| `person_directory` | `person_id` | Sem mudança (16 008 linhas, 7 índices; serve também lista de partidos e sitemap de pessoas) | 6 a 10 (relatório) |
| `person_profile_snapshot` | `person_id` | **Ampliado a todas as pessoas públicas** (retira o filtro `SCOPE_SQL`); 13 leituras gravadas como hoje | 25 a 60 (estimativa: ~700 pessoas ricas × 14 KB ≈ 10 MB, mais ~15 mil pessoas leves × 1,5 a 3 KB) |
| `person_proposition_page` | `(person_id, page)` | Páginas de 100 proposições com eventos (até 101 por item) e dados do detalhe da Câmara; substitui `fetch_person_propositions` (`public_propositions.py:9`) para qualquer página (hoje só a 1, e só abaixo de 100 000 caracteres) | 15 a 30 (estimativa; 166 mil vínculos) |
| `person_vote_context` | `person_id` | Exercícios e recibos de cobertura de votos, que a rota de votos hoje lê de `office_exercise`/`person_career_coverage_receipt` | 3 a 5 |
| `political_dashboard_partition` | `(year, territory_code, institution_code)` | Cópia de `political_dashboard_annual` (relatório: 26,1 MB, dos quais 18,3 de TOAST) | 26 |
| `political_dashboard_territory_history` e `political_dashboard_territory_catalog` | `territory_code` | Cópias das duas tabelas pequenas | < 1 |
| `majority_panorama_document` | 1 linha | Sem mudança | < 1 |
| `dataset_release` | `name` | Sem mudança | 0,02 |

Orçamento do Supabase (MB):

| Item | Regime | Pico no build |
| --- | --- | --- |
| `pg_catalog` e demais schemas (relatório) | 39 | 39 |
| `knowledge` (outro projeto; decisão D4) | 29 | 29 |
| Serving, caso central (10 + 40 + 25 + 5 + 26 + 1) | 107 | 107 |
| Cópia em staging do maior dataset durante o swap (`builder.py:46-56`, `DROP`+`RENAME`; o relatório já adverte do pico) | 0 | 40 |
| **Total central** | **175** | **215** |
| Caso pessimista (serving × 1,5) | 228 | 268 |
| Margem até 400 MB (pessimista, no pico) | | 132 |

Alerta operacional sugerido: aviso do publicador se `pg_database_size` passar de 300 MB.

### 2.4 Por que "núcleo canônico mínimo no Supabase" não cabe

Conjunto mínimo para o site ler sem serving profundo, após as ações seguras da auditoria: `person` 13,6; `person_fact` (sem `tse:*`) ~8; afiliação ~12; candidatura ~14; bens 15; `proposition` ~56; `proposition_person` 39,7; `source_record` compacta ~85 (estimativa: remover `payload`, mover `storage_reference` para o artefato); painel 26; identificadores 10,5; demais ~5. Soma: cerca de 285 MB. Com serving (107) e sistema (68): cerca de 460 MB em regime e cerca de 500 MB no pico. Contraria a meta. Por isso o canônico sai por inteiro, não por partes.

## 3. Idempotência, reconciliação, histórico e proveniência sem payload no Supabase

A solução mais simples é que **nada disso muda de lugar lógico**: reconciliação (`db/ingestion/reconcile.sql`: classificação `new/unchanged/changed/stale/conflicting` por `source_id + entity_kind + external_key + content_sha256`), `ingestion_entity_version`, `ingestion_artifact_entity` e `source_record` continuam no Postgres local, com os mesmos índices únicos (os 64 MB, 36 MB e 32 MB de índices únicos da auditoria deixam de contar contra o limite). O Supabase não precisa de hash de ingestão, porque não participa da ingestão.

Como cada exigência do `AGENTS.md` é atendida:

| Exigência | Mecanismo |
| --- | --- |
| Dados só chegam às projeções após normalização, validação e identificação de fonte/data | A ordem do pipeline continua: bruto, normalização/validação, ingestão local, só então publicação. O publicador rejeita linha de dataset sem `source_url` (ou chave de fonte) e sem data de observação/`as_of`. Teste de contrato por dataset. |
| Mudanças mantêm histórico | `ingestion_entity_version` e `ingestion_artifact_entity` locais, com export mensal para Parquet (`data/archive/<tabela>/ano=AAAA/`, manifesto com SHA-256 e contagem, padrão de `service/analytical_datasets/storage.py`) e cópia em Storage |
| Ausência em arquivo não prova saída do cargo | Inalterado: regras de reconciliação e `stale/conflicting` locais. O dataset serving não deriva "saída" de ausência |
| Rastrear o que o site mostrou | Nova tabela **local** `serving_publication_log` (`dataset_name`, `version`, `as_of`, `row_count`, `published_at`, `canonical_watermark_by_source` com o maior `ingested_at` por fonte). A `version` é o `md5` já gerado por `_measure` (`builder.py:79-86`) e gravado em `dataset_release` |
| Evidência por fato exibido | Cada item do snapshot já traz `source_url` e datas (campos lidos de `source_record`); a conferência acima impede publicar item sem eles |
| Testes não deixam dados fictícios na produção | O alvo dos testes passa a ser o Postgres local ou um schema isolado; o Supabase só recebe o publicador |
| Dados pessoais | `person_document_identity`, `candidate_document` e arquivos brutos com CPF/título ficam só na máquina |

Variante com hashes compactos, caso a máquina local um dia tenha disco restrito: manter só `(source_id, entity_kind, external_key_hash bytea(16), content_sha256 bytea(16), source_generated_at)` por entidade (estimativa ~45 MB para 276 mil linhas contra 238 MB atuais) e arquivar `normalized_data` em Parquet endereçado por hash. Não recomendo agora: toca em `db/ingestion/*.sql` (1125 linhas) e em `record_lookup.py` sem ganho para o limite do Supabase.

## 4. Fluxo de dados novo

```
fonte oficial
  -> crawler (src/crawlers/<fonte>/)                    data/<fonte>/ bruto, SHA-256, imutável
  -> normalização + validação (service/data_validation) staging NDJSON + quarentena (data/...)
  -> ingestão (service/ingestion) no Postgres LOCAL      canônico, versões, proveniência
  -> export histórico (service/archive_export)           Parquet em data/archive/ -> Storage (backup)
  -> publicação de datasets (service/serving)            lê LOCAL, escreve Supabase: staging, swap, release
  -> site (Vercel) lê só se_liga_brasil_serving          + Parquet de votos no Storage (já existente)
```

Mudanças de código (resumo, nomes conforme `AGENTS.md`):

- `src/database/operations.py:17` e `public_read_connections.py:47`: duas variáveis, `SE_LIGA_BRASIL_CANONICAL_DATABASE_URL` (pipelines) e `SE_LIGA_BRASIL_SERVING_DATABASE_URL` (publicador e site), ambas com fallback para `DATABASE_URL`. Sem as novas variáveis, comportamento idêntico ao de hoje (reversível).
- `src/service/serving/publisher.py` (novo): `publish_serving_datasets(canonical_connection, serving_connection, as_of)`. As fábricas de spec (`registry.py:SpecFactory`) passam a receber a conexão canônica; `build_dataset` (`builder.py:40`) recebe a conexão de serving e mantém transação, lock consultivo, staging, swap e release. Datasets hoje em `insert_sql` (`person_directory`, SQL no próprio banco) passam a `rows` em streaming via `COPY` (o builder faz `executemany` em lotes de 1000, `BATCH_SIZE`, suficiente para 16 mil linhas, lento para 166 mil). Se a versão (`md5`) não mudou, só atualizar `as_of` em `dataset_release` (evita recriar tabela e reduz pico).
- Datasets novos em `src/service/serving/`: `person_proposition_page.py`, `person_vote_context.py`, `political_dashboard_partition.py`. Ampliar `person_profile_snapshot.py:34` (escopo).
- Leitores: `person_profile_loader.py`, `public_people_directory.py`, `political_dashboard_*` e `majority_panorama_reader.py` leem do serving e **não** caem para o canônico. Sem release válida, aceitam release com até N dias de idade (decisão D2; hoje `current_release(..., max_age_days=1)`, `release.py:19`) e mostram a data `as_of`. Sem nenhuma release, resposta 503 já existente (`TEMPORARILY_UNAVAILABLE`).
- Derivações dependentes de data (idade, tempo de mandato, cargo atual) continuam em Python no momento da leitura, como já exige o snapshot (`person_profile_snapshot.py` docstring). Só filtros pré-calculados (cargo atual em `person_directory`) envelhecem com a release.
- Arquivamento: `src/service/archive_export/` (novo serviço) e `src/database/archive_export.py` (adaptador). Padrão de manifesto e troca atômica do `analytical_datasets`; o limite de 256 MiB do repositório analítico não vale aqui, usa-se orçamento próprio.

Execução (máquina local, sem hospedagem nova):

- Um `systemd --user timer` diário (a unidade de usuário `deploy/se-liga-brasil-voting-worker.service` já mostra o padrão; `loginctl enable-linger` já está em uso) executa, na ordem: coleta/ingestão por fonte, builds anuais do painel (`scripts/build_*`), `publish_serving_datasets`, export Parquet quando há mudança, verificação de saúde. Travas por fonte já existem (`repository.py` advisory lock por fonte).
- Falha em uma fonte não bloqueia as demais nem a publicação; falha de publicação deixa a release anterior servindo (garantia atual do builder: tudo numa transação, `builder.py:40-50`).
- O gatilho por escrita (`scripts/serving_rebuild_trigger.py`, `application/cli.py:215`, `enrichment.py:34`, `senado_history.py`) passa a chamar o publicador.
- A fila de votos hoje usa `pg_cron` no Supabase (`docs/pipeline-votacoes-agendamento.md`). No alvo, o enfileiramento (`voting_refresh_job`, `enqueue_voting_refresh`) fica no Postgres local e o disparo no timer (decisão D6).
- Máquina desligada: as releases envelhecem até N dias; o site continua no ar com a data exibida. Depois disso, o comportamento é o decidido em D2.

Vercel: nada de novo na implantação (`vercel.json` exclui `data/**`). Variáveis: `SE_LIGA_BRASIL_SERVING_DATABASE_URL` (conexão do pooler, porta 6543) e as credenciais de Storage já usadas. Recomendado criar papel `serving_reader` com `USAGE` no schema e `SELECT` nas tabelas de serving (o builder já ativa RLS e revoga `PUBLIC` em cada staging, `builder.py:63-65`; será preciso conceder `SELECT` e política de leitura ao papel a cada build). Hoje a Vercel usa a credencial administrativa; isso passa a ser corrigível porque o banco só terá dados já públicos.

## 5. Plano de migração

Cada etapa deixa o site funcionando. O canônico do Supabase só é apagado na última etapa.

| # | Etapa | Reversão | Aceite |
| --- | --- | --- | --- |
| E0 | Backup: `pg_dump -Fc` do Supabase (leitura), cópia em disco e em Storage criptografada; restaurar no PostgreSQL 17 local. Nada muda em produção | Descartar o banco local | Contagem por tabela e hash de amostra (por exemplo `md5` ordenado em `person`, `source_record` por id) iguais; `pytest -m integration` verde contra o local |
| E1 | Duas variáveis de conexão com fallback; `.env` aponta o canônico ao local em modo sombra (somente leitura de teste) | Remover variáveis | Suíte completa verde; comportamento idêntico sem as variáveis |
| E2 | `publisher.py` (origem local, destino Supabase) com teste sem rede e teste de falha no meio (release anterior intacta) | Voltar a `rebuild_serving_datasets` | Rebuild idempotente (mesma `version`); falha injetada não altera `dataset_release` |
| E3 | Novos datasets e snapshot para todas as pessoas, publicados ao lado do caminho atual. Piloto mede os MB reais antes de publicar tudo | `DROP` das tabelas novas | Tamanho real dentro de 1,5 × a estimativa; paridade de HTML idêntico entre serving e caminho canônico em amostra estratificada (pelo menos 200 pessoas: ricas, só bens, sem cargo, alias; todas as abas e páginas de proposições) |
| E4 | Leitores com modo `serving_only` (variável de ambiente) em Vercel preview, contra um banco que só tem serving | Variável volta a `serving_then_canonical` | Todas as rotas da seção 1 respondem 200/ETag igual; 503 controlado sem release |
| E5 | **Virada dos pipelines** para o Postgres local; Supabase canônico congelado (sem escrita). Dois a sete dias de execução diária com o timer | Apontar pipelines de volta ao Supabase (a cópia congelada fica defasada, então exige reexecução das fontes do período) | Sete execuções diárias sem divergência; `serving_publication_log` preenchido; sem desvio de contagem nas fontes |
| E6 | Observação de 14 dias; depois, no Supabase: `DROP TABLE` das tabelas de ingestão e do restante do canônico, `DROP SCHEMA se_liga_brasil`; medir | Restaurar do dump (E0 atualizado), que só cabe no plano Pro ou em outro banco: ver decisão D7 | `pg_database_size` < 250 MB; site sem erro por 7 dias |
| E7 | Export Parquet mensal do histórico (`ingestion_entity_version`, `ingestion_artifact_entity`, `person_activity_context`, `tse:*` de `person_fact`) e rotina de backup | Parar o export | Manifesto com SHA-256 confere; restauração de uma tabela testada |

Riscos principais:

1. **Banco acima do limite durante E3 a E6.** O banco continua em cerca de 1340 MB até E6. Se o Supabase já bloqueia escrita acima de 500 MB, o publicador falha. Verificar no painel antes de E3. Mitigação: alívio parcial seguro após E0 (derrubar os cinco índices sem leitura, cerca de 39 MB, e `person_activity_context` + `ingestion_artifact_entity`, cerca de 82 MB, que o site não lê), ou Pro por um mês (D1).
2. **Tamanho do snapshot de todas as pessoas.** É a maior incerteza (25 a 60 MB). O piloto de E3 mede; o teto já existente de 100 000 caracteres por linha limita o pior caso.
3. **Defasagem.** Release só é gerada com a máquina ligada. Mitigação: tolerância N dias com a data visível; alerta quando a última release passa de N.
4. **Máquina local como ponto único de falha.** Mitigação: backup E0/E7 e D3.
5. **Papel e RLS.** O site passa a depender de grants que o builder precisa reaplicar a cada swap; testar com papel não administrativo em E4.
6. **Pausa do projeto gratuito por inatividade.** Projetos gratuitos do Supabase são pausados após inatividade prolongada (confirmar o prazo vigente); o tráfego do site mantém o projeto ativo, mas a retenção só depende disso se o site parar.
7. **Perda de dados brutos.** `data/` tem 22 GB sem backup conhecido (relatório). Tudo que for só local precisa de política própria (D3).

## 6. Alternativas descartadas

| Alternativa | Por que não |
| --- | --- |
| Só aplicar as ações A a E da auditoria (índices, `pg_repack`, nulificar duplicatas) | Termina em cerca de 860 MB (relatório, seção 5), 360 MB acima do limite |
| Tirar do Supabase só a camada de ingestão e manter o canônico (variante "enxuta") | Cerca de 460 MB em regime e cerca de 500 MB no pico (seção 2.4). Exigiria ainda reescrever `source_record` e o formato de chaves |
| Esvaziar `source_record.payload` e `ingestion_entity.normalized_data` e usar só hash (saída 2 do relatório) | Mesmo problema de tamanho do item anterior, perde o payload sem substituir a fonte da verdade e só funcionaria com Storage antes (risco alto, C1/C2 do relatório) |
| Plano Pro do Supabase (cerca de US$ 25 por mês; confirmar preço e franquia) | Resolve o limite, mas não os 22 GB sem backup, mantém o custo para sempre e não separa ingestão de leitura. Fica como **contingência** de curto prazo para atravessar E3 a E6 (decisão D1) |
| Segundo projeto Supabase gratuito para a ingestão | Mesmo limite de 500 MB; o canônico tem 1,27 GB |
| Neon, Render Postgres ou outro Postgres gratuito para o canônico | Limites de armazenamento e expiração semelhantes ou piores (`docs/hospedagem-gratuita.md` já registra a expiração de 30 dias do banco gratuito do Render); mais uma conta e credencial sem ganho sobre o disco local |
| DuckDB/Parquet como banco canônico | Reescreveria 1125 linhas de SQL de ingestão, constraints, advisory locks e transações atômicas (psycopg) sem necessidade; DuckDB local já é o formato de análise, não o de escrita concorrente |
| Armazenar tudo em Storage/Parquet e ler Parquet por requisição | Storage de 1 GB não comporta o histórico completo e a leitura por visita foi descartada (`repositorio-analitico-local.md`); latência e custo de checagem de hash por partição |
| Cloudflare R2 ou outro bucket com cartão | Contraria a restrição de não usar cartão (`hospedagem-gratuita.md`) |
| Compactar `person_data_gap` e reduzir churn só no Supabase | Ganho de 35 a 45 MB; resolve sintoma, não a causa (fila de pipeline no banco de leitura) |

## 7. Decisões pendentes da usuária

- D1. Confirmar o rumo: PostgreSQL 17 local como canônico (recomendado), ou Pro como alternativa permanente. E aceitar Pro por um mês como ponte, se o Supabase já estiver bloqueando escrita.
- D2. Defasagem tolerada pelo site (sugestão: 3 dias, com a data de atualização visível) e o que mostrar quando não houver nenhuma release.
- D3. Backup fora da máquina: onde guardar (disco externo, segunda máquina, Storage criptografado) e quais partes de `data/` são reproduzíveis (os 17 GB do TSE vêm do catálogo oficial pelo hash; `alesp`, `senate-annual-reports`, `political-orientation` talvez não).
- D4. Schema `knowledge` (29 MB, outro projeto no mesmo banco): manter, arquivar `audit_log` (17,9 MB) ou mover.
- D5. Perfil público de todas as ~16 mil pessoas no serving (recomendado), ou só das que têm dado rico e uma página sem dados para as demais.
- D6. Mover o enfileiramento de votos de `pg_cron` do Supabase para o timer local.
- D7. Autorizar a remoção do canônico do Supabase (E6). Depois dela, voltar ao plano gratuito com o canônico exigiria o Pro.
- D8. Verificar no painel: estado atual de bloqueio acima de 500 MB e uso atual do bucket `voting-datasets` (soma com backups deve caber em 1 GB).
