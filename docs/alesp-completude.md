# ALESP: completude institucional e autoria local

Implementação em 17/10/2026. Os arquivos originais permanecem inalterados. Não houve ingestão massiva em produção nesta frente.

## Contrato executável

`collect_alesp_enrichment(connection, person_ids=None, fields=None)` recebe os alvos e campos do orquestrador. A folha existente só é executada quando `current_salary` é solicitado. `current_public_office`, `current_political_party` e `political_activity` usam a evidência local via `collect_alesp_local_enrichment(repository, storage_directory, person_ids=None, fields=None)`.

O coletor local valida SHA-256 dos arquivos referenciados e dos conjuntos de pesquisa contra os manifestos já existentes. Produz bundles derivados e NDJSON privados separados, sem reescrever XML/ZIP originais. O repositório genérico continua responsável por reconciliação, registros de fonte, lotes e idempotência.

## Identidade e cargo atual

Somente resoluções `matched` com `official_subjects` entram na projeção. A fotografia local contém 100 resoluções de recebedores de folha, mas apenas 89 têm esses perfis institucionais e a ponte técnica para os autores. Os outros 11 não são vinculados por aproximação de nome ou pela presença histórica na folha.

O perfil fornece `isEmExercicio`, salvo como `person_fact.current_public_office_observation`, administrativo e verificado, com `inExercise`, `observedOn`, `institutionCode=alesp`, `officeKind=state_deputy` e UF SP. A projeção compartilhada `person_current_public_office` atualiza os campos da pessoa introduzidos pela migração 0013. `false` aqui descreve somente não exercício na ALESP e não prova ausência de qualquer cargo público.

`listaMandatos` fornece o período institucional: ele é projetado em `office_term`, sem criar `office_exercise`. O início da legislatura não comprova a data individual de posse. Não há data individual de exercício suficiente nos perfis usados; o fato de observação permite afirmar exercício atual sem inventar uma data inicial. O último dia informado do período é preservado como limite exclusivo no dia seguinte.

## Partido

O partido corrente com código único explicitamente aberto no perfil é projetado como observação administrativa em `political_party_affiliation`, escopo `institution:alesp`. A validade informacional SCD2 termina na observação seguinte para a mesma pessoa e escopo. Ela não é a data jurídica de desfiliação. As listas de filiações e suas datas originais permanecem integralmente no fato institucional para futura normalização histórica e reconciliação; não convertemos uma data de fim de semântica não documentada em limite jurídico exclusivo.

## Proposituras e autoria

Os conjuntos locais usados são `61_deputados.xml`, `81_documento_autor.zip` e `56_proposituras.zip`. A ponte técnica é `IdDeputado` do perfil pessoal verificado → `IdSPL` do roster oficial → `DocumentoAutor.IdAutor`. IDs externos servem somente ao cruzamento do arquivo; não são gravados como identidade da pessoa. Nome isolado nunca escolhe o `person_id`.

A leitura XML é incremental, limpa os filhos da raiz a cada registro e junta documentos em índice SQLite temporário, removido ao terminar. Duplicatas de `(documento, person_id)` são descartadas. Somente documentos com autores pessoalmente verificados são normalizados e enviados em lotes de 500 ao PostgreSQL. A projeção salva `proposition` e `proposition_person.role=author`, com status `unknown`: autoria não prova aprovação, lei resultante ou impacto político. `DtPublicacao` é preservada no registro fonte e não é inventada como data de apresentação. O código de natureza é explícito como `alesp_natureza:<IdNatureza>`, sem adivinhar siglas.

Para A relações de autoria e P documentos, a leitura exige O(A+P); o índice B-tree temporário adiciona inserções/consultas O(log M), onde M são relações dos autores selecionados. Memória é limitada ao roster/resoluções, cache SQLite de 4 MiB, um registro XML e lotes de ingestão; disco temporário O(M). Não é O(1) para ler toda a fonte. Nenhuma requisição HTTP é feita nessa etapa local.

## Validação

Cinco testes unitários verificam incerteza temporal, ponte pessoal obrigatória, rejeição de ambiguidade, deduplicação, checksums, staging e despacho da projeção. Um teste PostgreSQL em schema isolado com rollback confirmou idempotência, flag/cargo da pessoa, mandato sem exercício inventado e autoria com status desconhecido. Os seis testes passaram. A suíte ALESP existente também passou: 15 testes unitários, dois testes de banco sem configuração foram ignorados nessa execução. Ruff e revisão estrutural sem achados nos arquivos desta frente.

A varredura completa somente leitura dos arquivos reais encontrou 166.502 relações de autoria únicas para as 89 pessoas com ponte institucional verificada, sem escrever no banco ou chamar fontes remotas. A ingestão dessas relações está disponível pelo coletor, mas não foi disparada em produção.
