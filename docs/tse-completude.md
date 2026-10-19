# Enriquecimento direcionado TSE

`collect_requested_tse_data(connection, storage, targets)` recebe pessoas internas e campos solicitados. Cada item contém `person_id`, `election_year` e `fields` (nascimento, escolaridade, nome completo, bens ou patrimônio declarado). O wrapper `collect_declared_assets` permanece compatível.

Os arquivos originais de `data/tse/download-plan.json` são reaproveitados, sem alteração. Downloads faltantes são agrupados por ano e tipo, não por pessoa. A leitura é streaming com índice SQLite de candidaturas para selecionar bens. Esse relacionamento técnico entre linhas não identifica pessoas: candidaturas só são aceitas mediante CPF validado com fingerprint já associado à pessoa solicitada, ou nome completo/data de nascimento únicos na base. Documento divergente não cai no fallback de nome.

A projeção existente mantém registros de fonte e fatos. Um reparo adicional em lote preenche somente nascimento/escolaridade nulos, a partir de fatos TSE já associados à pessoa; nascimento com múltiplas versões continua sem correção automática. Artefatos já ingeridos podem ser reutilizados e seus fatos reparar projeções nulas, sem novo download.

Conflitos entre declaração explícita de ausência de bens e linhas de patrimônio são retornados como `DECLARATION_CONFLICT_REQUIRES_REVIEW`. Reprocessar arquivos pode incorporar republicações disponíveis; não apaga bens, não converte ausência em zero e não resolve automaticamente os 31 conflitos previamente auditados. Eles permanecem pendentes até evidência oficial ou revisão. Escolaridade é declaração eleitoral, não verificação de diploma. Resultado eleitoral não prova exercício atual.

Limitações: pessoas sem CPF validado e sem nascimento suficiente para identificação segura não são enriquecidas automaticamente. Nome completo não é sobrescrito pelo reparo. Os arquivos locais podem repetir a mesma ausência de informação; nesses casos a fila continua aberta e o orquestrador aplica cooldown, sem inventar dados. Não foi executada ingestão em massa em produção.

Custo: varredura O(n) nas linhas selecionáveis de cada arquivo, com memória de streaming limitada e escopo pessoal O(p); consultas de identidade e reparo são em lote. Não há consulta remota por candidato.
