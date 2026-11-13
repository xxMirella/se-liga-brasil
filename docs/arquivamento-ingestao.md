# Arquivamento local verificado do banco (antes de qualquer remoção)

Regra: toda informação que está no banco também existe em `data/` (cópia local verificada). Nenhuma migration destrutiva (R1-R6, 0025, 0026, 0028, 0029, 0030 ou qualquer `DROP`/`UPDATE ... NULL` de dados) é aplicada sem um snapshot completo verificado.

Serviço: `src/service/archive_export/`. CLI: `scripts/archive_ingestion_data.py`. Testes: `tests/test_archive_export_integration.py`, `tests/test_source_record_payload_guard.py`.

## Formato

- Um arquivo `.ndjson.gz` por tabela (ou fatia nomeada), em `data/database_snapshot/<UTC-timestamp>/` (`data/` está no `.gitignore` e `scripts/check_tracked_files.py` rejeita qualquer arquivo versionado nele).
- Cada linha: `{"row_sha256":"<hex>","key":[<chave primária>],"row":{<linha inteira>}}`. `row` é o texto exato de `to_jsonb(linha)::text` do PostgreSQL (uuid, timestamptz, numeric, arrays, jsonb e bytea voltam sem perda) e `row_sha256` é o SHA-256 desse texto, que o banco recalcula com `sha256(convert_to(to_jsonb(t)::text,'UTF8'))`.
- `manifest.json`: por arquivo, tabela, filtro (`filter_sql`), colunas, chave primária, nº de linhas, bytes, `file_sha256`, `row_hashes_sha256` (hash dos hashes de linha, em ordem), data/hora; no topo, versão do servidor, `schema_fingerprint_sha256` (hash de todas as tabelas/colunas/tipos do schema), `repository_migration_head` e o isolamento usado.
- Escolhi NDJSON.gz e não Parquet (duckdb já é dependência): o Parquet exigiria mapear cada tipo (jsonb, arrays, uuid, bytea) e perderia a igualdade byte a byte com o banco que o `verify` usa; NDJSON.gz é legível com `zcat`, sem dependência.
- Tabelas geradas (colunas `GENERATED ... STORED`) são exportadas sem a coluna gerada. `se_liga_brasil_serving` entra só com `dataset_release` (versões de release); as demais tabelas de serving são reconstruíveis (`scripts/rebuild_serving_datasets.py`).
- Tamanho estimado (não medido em produção): o banco tem 1,3 GB, mas índices (~100+ MB) e espaço morto não são exportados; JSON repetitivo comprime 8-12x com gzip. Estimativa: 150 a 300 MB comprimidos no total. O `export` imprime bytes por arquivo; `plan` lista o tamanho de cada tabela antes.

## Ordem obrigatória

1. **Snapshot completo** (somente leitura, uma transação `REPEATABLE READ`, cursor no servidor, memória constante):
   ```
   python scripts/archive_ingestion_data.py export --scope snapshot
   ```
   Cria `data/database_snapshot/<UTC>/` com todas as tabelas de `se_liga_brasil` (pais antes de filhos), `se_liga_brasil_serving.dataset_release` e a fatia `source_record@payload_without_readers` (as linhas que a 0028 anula). Use `--output-dir` para outro diretório e `--table nome` (repetível) para refazer só algumas tabelas. O diretório precisa estar vazio.
2. **Verify** (somente leitura):
   ```
   python scripts/archive_ingestion_data.py verify --archive-dir data/database_snapshot/<UTC>
   ```
   Por arquivo: sha256 e bytes do arquivo, contagem, hash de cada linha, hash agregado, e comparação linha a linha (chave + hash) com o banco na mesma ordem. Na fatia de `source_record` confere também `content_sha256 == hash_content(payload)` (função `storage.files.hash_content`). Código de saída 0 só se tudo bate; então imprime `VERIFIED manifest_sha256=<hash>` e grava `verification.json`. Se colhedores gravaram entre o export e o verify, tabelas ativas aparecem como divergentes: pare os crawlers, refaça export e verify.
3. **Só então** aplique migrations destrutivas. Cada uma deve citar o `manifest_sha256` verificado. A 0028 exige `SET se_liga_brasil.verified_archive_manifest_sha256 = '<hash>'` na mesma sessão; sem isso não altera nada e emite WARNING.
4. Depois de uma migration destrutiva o `verify` do snapshot antigo passa a divergir nas tabelas/colunas removidas: isso é esperado; o arquivo é a fonte.

Exceções a lembrar: o snapshot deve ser feito ANTES das migrations 0025 (`ingestion_entity_version`), 0029 (`ingestion_artifact_entity`) e 0030 (`person_activity_context`); `export --scope removal-targets` (fatia R4 mais essas tabelas, ignorando as já removidas) existe para quando só elas importam.

## R4: migration 0028 (anular `source_record.payload` dos tipos que ninguém lê)

- Lista única: `SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD` em `src/service/archive_export/source_record_types.py`: `alesp:alesp_propositions`, `alesp:alesp_attendance`, `tse:asset`, `tse:complement` (tipo = prefixo de `external_key` antes do `:`, por `source.code`).
- **tse `history` ficou de fora** (~8 MB), ao contrário do plano original: `electoral_candidacy.source_record_id` pode apontar para registros `history` (`db/ingestion/identities.sql` grava a candidatura nos dois tipos) e `person_identity.py`, `enrichment.py` e `crawlers/tse/enrichment.py` leem `payload` por esse vínculo. `candidate`, os tipos Câmara, folha, senado e alerj também ficam.
- Guarda: `tests/test_source_record_payload_guard.py` falha se um arquivo novo de `src/`, `db/` ou `scripts/` ler `<alias>.payload`/`payload->` junto de `source_record` sem estar em `KNOWN_PAYLOAD_READERS`, e se a lista Python divergir da migration/rollback.
- Aplicar (psql, autocondicional, cada lote de 20000 ids confirma sozinho; não use transação externa nem o executor `db-migrate`, que envia o arquivo como uma só instrução):
  ```
  psql "$DATABASE_URL" -c "SET se_liga_brasil.verified_archive_manifest_sha256='<hash>'" -f db/migrations/0028_null_unread_source_record_payload.sql
  ```
  Só altera linhas com `storage_reference IS NOT NULL` (o CHECK `payload IS NOT NULL OR storage_reference IS NOT NULL` continua valendo). Idempotente; reexecutar periodicamente, porque `reconcile.sql` ainda grava `payload` de registros novos desses tipos. O espaço só volta após `VACUUM FULL`/`scripts/maintenance_reclaim_table_bloat.py`.
- Rollback: restaurar do arquivo e rodar a trava:
  ```
  python scripts/archive_ingestion_data.py restore --archive-dir data/database_snapshot/<UTC> \
    --table source_record@payload_without_readers --mode fill-null-columns --column payload --dry-run
  python scripts/archive_ingestion_data.py restore --archive-dir data/database_snapshot/<UTC> \
    --table source_record@payload_without_readers --mode fill-null-columns --column payload
  psql "$DATABASE_URL" -f db/rollbacks/0028_restore_source_record_payload.sql
  ```
  O arquivo SQL falha enquanto alguma linha dos tipos listados ainda tiver `payload` nulo.

## Restaurar

`restore` escreve no banco (use a mesma `DATABASE_URL`, sem pooler de transação se possível). Antes de tocar no banco ele confere o sha256 e o hash de cada linha do arquivo. Cada lote de 1000 linhas confirma sozinho; é seguro repetir.

- `--dry-run`: executa tudo numa transação que sofre rollback e informa `rows_changed` (quantas linhas entrariam/seriam preenchidas).
- `--mode insert` (padrão): insere só as linhas cuja chave primária não existe (`ON CONFLICT DO NOTHING`, nunca sobrescreve); ids de identidade são preservados (`OVERRIDING SYSTEM VALUE`) e a sequência é avançada para o maior id. Tabela sem chave primária só é restaurada se estiver vazia.
- `--mode fill-null-columns --column <coluna>` (repetível): `UPDATE` que preenche, nas linhas existentes, só as colunas hoje nulas (`coalesce`); nunca sobrescreve valor.
- Tabela inteira: `restore --archive-dir <dir> --table <tabela>` (para um schema inteiro, sem `--table`; a ordem pais-antes-de-filhos já está no manifesto). Se a tabela foi recriada por migration de rollback, recrie-a antes (`db/schema.sql` + migrations); o arquivo só tem dados.
- `--table` aceita `tabela`, `tabela@fatia`, `schema.tabela@fatia` ou o nome do arquivo.
- Restaurar para outro schema de teste: parâmetro `schema=` do serviço (usado nos testes).

### Por alvo de remoção
- `ingestion_entity_version` (inclui `first_ingested_at` e `normalized_data`): `restore --table ingestion_entity_version` após recriar a tabela (0003) e as linhas de `ingestion_entity`/`source_record` já existirem (FKs).
- `ingestion_artifact_entity`: idem; depende de `ingestion_artifact`, `ingestion_entity` e `source_record`.
- `person_activity_context`: idem; depende de `person`, `source`, `source_record` e das tabelas de afiliação/candidatura/mandato.
- Colunas removidas de uma tabela que continua existindo (por exemplo `ingestion_entity.normalized_data`): recrie a coluna como anulável e use `--mode fill-null-columns --column normalized_data`.

## Limites conhecidos

- Os dados exportados refletem o instante do snapshot; o que for gravado depois não está no arquivo.
- `verify` compara com o estado atual do banco; mudanças legítimas posteriores aparecem como divergência.
- O diretório `data/` é só local: faça cópia fora da máquina (disco externo) antes de apagar dados em produção.
