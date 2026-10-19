# Histórico legislativo da Câmara

Extensão opt-in em `crawlers.camara.legislative_history`. Não altera o despacho anterior, não executa coleta massiva e não afirma cobertura de toda a vida pública. Arquivos originais permanecem imutáveis. Não foi executada ingestão de produção nesta implementação.

## Fluxo operacional

`collect_legislative_history(acquisition, repository, proposition_keys, resolve_person=None, max_propositions=25)` recebe URLs oficiais de proposições já existentes, compartilhadas entre pessoas. Reutiliza `CamaraAcquisition`, downloader/cache, paginação limitada, `stage_records`, `IngestionRepository` e `CamaraProjectionWriter`.

Para cada documento único consulta detalhes, `/tramitacoes`, `/autores`, `/relacionadas` e `/votacoes`. A deduplicação acontece antes de HTTP. Cada página é normalizada, deduplicada e ingerida no mesmo fluxo de reconciliação. Falha de paginação propaga erro e não retorna conclusão; páginas concluídas podem ser reaproveitadas na retomada. Não há checkpoint remoto próprio: a retomada usa cache de aquisição e idempotência de ingestão existente.

O limite de documentos é explícito. A responsabilidade do planejador externo é entregar lotes limitados; um iterável acima do limite lança `CAMARA_PROPOSITION_BUDGET_EXCEEDED`, mantendo ingestões anteriores idempotentes. A API não deve ser chamada individualmente para cada pessoa quando documentos se repetem.

## Tabelas preenchidas

- `source_record` e tabelas de artefatos/execução: reconciliação, evidências e normalizações de todos os recursos.
- `proposition`: complementação de ementa/data de apresentação apenas para documentos existentes. Não cria documentos relacionados sem coleta/validação própria e não interpreta texto de situação como aprovação final.
- `proposition_event`: tramitações com sequência oficial, órgão e descrição; decisões coletivas são eventos separados `collective_stage_decision`. O conteúdo normalizado da fonte preserva data de ocorrência, precisão diária quando pertinente, data de registro e indicador de aprovação.
- `proposition_person`: autor/coautor somente após resolução de identidade fornecida pelo chamador. O indicador `proponente` diferencia os papéis; ordem de assinatura sozinha não define autoria exclusiva. Corrige vínculo genérico anterior de autor quando a fonte comprova coautoria daquela mesma pessoa/documento.

`resolve_person(row)` deve retornar o UUID interno apenas depois de identificação pessoal revisada por serviço existente, ou `None`. Nunca usar o ID/URI do deputado como `person_id`, persistir esse ID pessoal na projeção, nem confirmar identidade apenas por nome. Sem resolver, autores são consultados mas não há vínculos pessoais novos; o resumo de páginas não significa identificação completa.

## Semântica e limites reais

Aprovação em comissão, de requerimento ou de emenda não implica aprovação final do projeto. O indicador `aprovacao=0` pode significar rejeição ou falta de quórum: permanece resultado desconhecido sem evidência suficiente. O estado agregado da proposição não é promovido automaticamente.

As datas/horas de tramitação são interpretadas no fuso `America/Sao_Paulo`. Decisões coletivas sem horário de ocorrência publicado usam início do dia somente como representação técnica em `proposition_event`; a precisão **dia** permanece no registro normalizado e deve ser respeitada na API pública, sem apresentar horário como fato comprovado. `dataHoraRegistro` não substitui ocorrência.

`urnFinal` permanece uma referência oficial à norma no detalhe normalizado. Relações oficiais entre documentos também permanecem como registros normalizados. **Não há inserção em `law`/`proposition_law`**: número, publicação, jurisdição e vínculo precisam de validação da norma antes da projeção. Não se presume conversão em lei pela semelhança textual ou por proposição relacionada.

**Não há inserção em `voting`/`person_vote` nesta etapa.** O endpoint de listagem pode não identificar o objeto real da votação. O modelo atual obriga uma proposição e horário exatos, sem preservar adequadamente objeto ambíguo ou precisão diária. Uma ampliação compatível deve registrar objetos candidatos versus proposições afetadas, método confirmado e precisão temporal; depois poderá projetar votos nominais apenas para identidades verificadas. Ausência de voto não vira ausência na sessão, voto contrário ou zero aprovações.

## Integração pendente

O dispatcher/CLI deve selecionar documentos existentes em lote, instanciar o repositório Câmara com o projetor já existente e chamar a função opt-in sob os mesmos locks/cooldowns/budgets do orquestrador. A função não cria conexão, não ignora cooldown e não é um serviço de completude. Não habilitar chamadas extras no fluxo antigo implicitamente.

Para grandes históricos, priorizar arquivos oficiais anuais de `votacoes`, `votacoesVotos`, `votacoesObjetos` e `votacoesProposicoes`; o downloader geral já pode adquiri-los. O parser streaming e planejamento por ano desses conjuntos ainda precisam ser implementados: a presente extensão usa endpoints para lotes pequenos de documentos e não substitui uma carga anual econômica.

## Custo e validação

Para D documentos únicos, P páginas e N registros, CPU O(D+N), memória O(D+B), com B registros de uma página. Consulta/deduplicação por chave tem custo médio O(1), mas ler N registros continua O(N). Rede: uma consulta de detalhe e quatro sequências paginadas por documento; endpoints não oferecem todos os detalhes em uma única chamada. O cache reduz downloads repetidos sem transformar esse custo em O(1).

Testes anônimos cobrem coautoria, identidade não verificada, aprovação acessória, indicador zero ambíguo, chaves permitidas, deduplicação antes de HTTP, limites e paginação interrompida. A revisão estrutural passou sem achados. Teste SQL em esquema isolado passou com rollback obrigatório: confirma evento único após reingestão e preservação de status desconhecido. Nenhum dado fictício permaneceu na produção. O escopo de staging inclui as chaves efetivamente resolvidas, permitindo reprocessar autores antes não identificados sem um falso cache de conclusão.

## Fontes oficiais verificadas

[API e conjuntos anuais oficiais](https://dadosabertos.camara.leg.br/swagger/api.html) e [guia oficial de votações](https://dadosabertos.camara.leg.br/howtouse/2020-02-07-dados-votacoes.html), consultados em 17/10/2026. Cinco respostas públicas pequenas da API confirmaram os campos de detalhes, autores, tramitações, relacionadas e votações; nenhuma pessoa foi inserida ou alterada na base.
