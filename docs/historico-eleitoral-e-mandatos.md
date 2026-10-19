# Planejamento de cobertura eleitoral e exercício

O serviço `service.public_career_coverage` implementa avaliação **somente de leitura** e planejamento em lotes de até 1.000 pessoas. Não faz coleta remota, não modifica arquivos originais, não executa migrações e não escreve pendências automaticamente.

## Contrato e uso

`assess_career_coverage(connection, person_ids, today, receipts=(), expected_scopes=())` lê candidaturas, mandatos institucionais e exercícios em três consultas para o lote inteiro. Retorna `assessments`, `resources`, `known_terms` e `career_beginning_verified=False`.

`CoverageScope` identifica pessoa interna, instituição, domínio, intervalo exclusivo ao final, fonte e partição. O chamador pode acrescentar expectativas verificadas por meio de `expected_scopes`. O domínio `elections` significa a consulta integral às candidaturas e aos resultados disponíveis naquela eleição/UF; o recibo não pode atestar resultados que o recurso não publica. Usar recibos parciais quando houver necessidade de complementação.

`build_observed_scopes(candidacies, exercises, today)` usa eleições efetivamente observadas e exercícios comprovados. Um resultado eleitoral positivo não vira mandato ou posse. O período institucional de um mandato sem exercício é devolvido como contexto em `known_terms`; precisa de investigação institucional, não é prova de atuação. Intervalos interrompidos permanecem separados, sem preencher anos de afastamento.

O primeiro fato disponível não prova o início real da carreira. Nenhum ano anterior é considerado automaticamente aplicável ou completo. Ausência de fatos deixa a carreira desconhecida. O chamador precisa fornecer escopo adicional a partir de fontes institucionais ou calendário oficial validado; este módulo não adivinha eleições anteriores, suplementares ou instituições por UF.

`plan_coverage(scopes, receipts, today, freshness_days=30)` distingue `not_assessed`, `partial`, `complete_for_period`, `outdated`, `unavailable`, `identity_unverified`, `not_applicable` e `future`. Uma partição futura não gera aquisição. Uma expectativa desconhecida permanece visível e não gera consultas sem fundamento. Prova de cobertura requer identificação validada, paginação/enumeração encerrada, abrangência da fonte e artefato verificado para o **mesmo intervalo**. Quantidade positiva de fatos e `EXISTS` não provam cobertura. Zero eventos só é conclusivo após consulta completa daquele escopo.

Recibos são um contrato explícito: o chamador deve extraí-los de metadados verificados da aquisição. O resumo atual `person_data_coverage`, isoladamente, não prova término de paginação e não é convertido automaticamente em recibo. Este trabalho não cria armazenamento paralelo para recibos.

## Recursos compartilhados e reutilização

As intenções são agrupadas por fonte/instituição/domínio/partição, com preferência por arquivos locais. Eleições TSE usam partições `ano/UF`; exercícios institucionais usam ano e intervalos efetivos. Pessoas diferentes recebem o mesmo recurso compartilhado.

`select_shared_tse_resources(plan, catalog_resources)` recebe os objetos `Resource` produzidos pelo descobridor TSE existente. Seleciona recursos de candidatos, complementos e histórico e deduplica por URL real. Um ZIP nacional atende várias UFs com uma única intenção de aquisição. Retorna recurso existente e conjunto de `person_ids`; não inventa identificadores pessoais externos nem cria um cliente HTTP adicional. O executor deve entregar os objetos ao downloader/cache/normalização/resolução de identidade existentes, respeitando limites, cooldown e bloqueios atuais.

A aquisição institucional de posse, afastamento, renúncia e retorno precisa adaptar suas evidências ao contrato. Uma lista nominal atual não prova ausência histórica, nem encerramento do exercício de quem deixou de aparecer.

## Integração com a fila existente

`overlay_political_activity_coverage(report, assessments, required_domains=("propositions", "votes", "laws"))` produz novo relatório com os outros campos preservados. Sem avaliações explícitas dos domínios esperados, mantém `political_activity=missing_or_unverified`. Cobertura eleitoral ou de exercícios, sozinha, nunca resolve atividade legislativa. O chamador deve fornecer todas as instituições e intervalos esperados e marcar domínios inaplicáveis com evidência, sem transformar ausência de fonte em inaplicabilidade.

O serviço de completude pode aplicar esse overlay ao relatório completo **antes** de chamar `database.data_gaps.persist_data_gaps`. Não chamar persistência com um relatório contendo apenas `political_activity`: o contrato atual resolve os demais campos omitidos. Não foi criada outra fila e não há alteração no schema de produção. O orquestrador deverá consumir as intenções e recalcular períodos após cada aquisição; essa ligação ainda precisa ser implementada no fluxo de delegação existente.

## Complexidade e limites

Construção de índices e deduplicação custam O(n + r), com n expectativas e r recibos; cada recibo só é examinado no seu escopo. A ordenação das pessoas dentro de cada recurso custa O(p log p) no pior grupo; não há comparação nominal quadrática. Memória O(n + r + p). São três consultas por lote, nunca uma por pessoa. O PostgreSQL não oferece promessa de O(1); índices existentes e planos devem ser medidos quando a integração passar a executar grandes lotes.

Limites conhecidos: recibos usam correspondência exata de intervalo, sem união automática de fragmentos; mudança do fim de período aberto exige recalcular a expectativa. O serviço ainda não fornece um inventário oficial completo de eleições suplementares, cronologia anterior ao primeiro fato, aquisição institucional ou atualização automática em produção. Esses limites permanecem pendências, sem declarar cobertura integral.
