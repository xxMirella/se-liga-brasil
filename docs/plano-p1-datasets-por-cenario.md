# P1 — datasets por cenário (cartões para o Trello)

Objetivo: substituir leituras caras do site por tabelas de leitura geradas pelos pipelines, em esquema próprio, com fallback para o caminho atual. Ordem: A → (B, D em paralelo) → C.

Regras comuns: migrations só aditivas e escritas, nunca aplicadas por agente (aplicação é da Mirella); sem `db push`; banco de produção só leitura nas investigações; derivação de regra de negócio continua em Python; todo leitor cai no caminho atual se não houver release válido (mais de 1 dia de idade ou ausente).

## Cartão P1-A — Base: esquema `se_liga_brasil_serving` e construtor atômico
- Migration `0023`: cria o esquema com RLS, sem acesso para `anon`, e `dataset_release(name, version, built_at, as_of, row_count)`.
- Construtor genérico em `src/service/serving/`: constrói em staging e troca por rename numa transação; grava a release.
- Gatilho: ao fim dos pipelines (TSE, Senado, coleta) e job diário.
- Aceite: reconstrução idempotente; falha no meio não altera o que está servido; testes sem rede.

## Cartão P1-B — `person_directory` (busca)
- Uma linha por pessoa (~16 mil): `person_id`, `slug`, `display_name`, `name_search` (sem acento, minúsculas), `uf[]`, `office_kinds[]`, `party_abbr`, `party_sort_key`, `state_sort_key`, `photo`, `as_of`.
- Índices: PK; `(party_sort_key, display_name, person_id)`; `(state_sort_key, ...)`; GIN em `uf[]`.
- `search_people` e a lista de partidos leem o diretório, com fallback à SQL atual.
- Aceite: teste de paridade (mesmos filtros e ordenações) contra a SQL atual.
- Depende de P1-A.

## Cartão P1-C — `person_profile_snapshot` (perfil)
- ~700 pessoas com dado rico: `person_id` (PK), `payload jsonb` com as linhas brutas das 13 leituras (`READ_NAMES`; a transação `read_snapshot` não entra no payload), `source_version`. A derivação continua em Python.
- Decidir proposições (paginação) lendo `fetch_person_propositions`.
- Pessoas sem snapshot seguem o caminho atual.
- Aceite: HTML do perfil idêntico entre snapshot e caminho atual numa amostra de pessoas.
- Depende de P1-A e P1-B.

## Cartão P1-D — `majority_panorama_document` (Panorama)
- Uma linha com o documento já montado por `build_majority_panorama`, gerada depois dos `build_*_annual`.
- `CachedMajorityPanorama` lê a linha e cai na montagem atual se faltar. ETag a partir de `dataset_version`.
- Aceite: documento serializado idêntico ao da montagem atual.
- Depende de P1-A.
