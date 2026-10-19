# Erros e limites da resolução de pendências

Auditoria em 17/10/2026, com leitura do código, dos relatórios de produção e de agregados do PostgreSQL. Nenhuma coleta foi reiniciada. As contagens abaixo representam a fotografia consultada, não uma promessa de cobertura nem uma contagem de erros por requisição.

## Resultado global e limite da execução

Há 63.084 pendências abertas em uma base de 15.448 pessoas. Somente duas pessoas satisfazem todos os oito campos mínimos. Atividade política é um diagnóstico adicional e também gera pendência, mas não integra esse mínimo.

A principal distinção operacional é que **62.088 pendências nunca tiveram tentativa; 996 tiveram pelo menos uma**. Portanto, não é correto atribuir toda a fila a falhas dos crawlers. Um despacho assume no máximo 1.000 tarefas, agrupa por fonte e pessoa e respeita cache, limites do conector, lease e cooldown. Os relatórios mostram execuções parciais, não uma varredura integral bem-sucedida.

Distribuição por campo na consulta global:

- Partido atual: 15.354, ausente ou não verificado.
- Cargo atual: 15.355, ausente ou não verificado.
- Salário atual: 15.445, sendo 15.345 sem pagamento e 100 com competência desatualizada.
- Atividade política: 15.444, ausente ou não verificada.
- Bens: 710 ausências e 31 conflitos; patrimônio tem as mesmas 741 pendências derivadas da declaração. Não são 1.482 pesquisas independentes.
- Nascimento e escolaridade: duas pendências de cada campo.

Nenhuma linha consultada tinha `is_processed=true`: as resolvidas são expurgadas. Não há retenção de fila concluída para reconstruir histórico de execução; os relatórios e fatos possuem responsabilidades distintas.

## Incidentes corrigidos, sem confundir com falhas ainda ativas

### Coautoria ALESP: `OPERATION_FAILED`, SQLSTATE `21000`

O primeiro lote de produção encontrou `CardinalityViolation`: várias autorias do mesmo documento tentavam atualizar a mesma proposição no mesmo comando. A projeção `db/ingestion/alesp_propositions.sql` passou a selecionar uma proposição por instituição/chave com `DISTINCT ON`, preservando os vínculos de autores em tabela própria.

Há comprovação posterior de execução local: 708 autorias novas, zero rejeições, zero requisições remotas e duas pendências resolvidas. Isso confirma a correção para o lote reprocessado; não comprova identidade de todos os autores do acervo. Não se deve marcar como resolvida a atividade de uma pessoa que ainda não tem autoria vinculada.

### Câmara: `CAMARA_PROPOSITION_SCHEMA_CHANGED`

O lote encontrou documento sem número. O normalizador aceita número ausente e a migração `0015_optional_proposition_number.sql` permite `proposition.number=NULL`; a identidade continua sendo a chave oficial, sem número inventado.

O código contém a correção, mas os relatórios examinados não comprovam retomada integral do lote remoto que falhou. Na consulta global, 24.018 tarefas em 6.005 pessoas ainda carregam esse código. **Isso não significa 24.018 erros de parser**: `postpone_source` propaga o primeiro código de falha do grupo para as tarefas abertas da fonte. Um novo despacho controlado deve comprovar a retomada. Manter pendente enquanto o fato solicitado não existir.

### Roteamento por candidatura futura

O roteamento passou a priorizar instituição confirmada e eleição anterior cujo período esperado ainda esteja vigente, antes da candidatura mais recente. A candidatura serve como pista de pesquisa; não confirma exercício.

Uma execução posterior do Senado confirmou perfil e exercício, resolveu duas de quatro tarefas e preservou as duas não suportadas. A correção está comprovada nesse recorte, não em todas as pessoas históricas. Usar apenas o cargo disputado fabricaria cargo atual.

### Falha remota não deve impedir o acervo local ALESP

O coletor agora ingere primeiro os artefatos locais e registra separadamente falhas da folha. O despacho por campo permite avançar atividade local durante cooldown remoto. O resultado com 708 autorias e zero HTTP comprova essa independência. Os campos sem evidência continuam abertos.

## Falhas e bloqueios ainda relevantes

### Fonte temporariamente limitada: Câmara, `HTTP_ERROR`, HTTP 429

O primeiro lote registrou uma resposta 429 e 33 pessoas adiadas. Havia também 99 pessoas sem correspondência institucional, categoria distinta da falha HTTP. O relatório não demonstra 134 requisições: `source_requests.camara=134` conta pessoas agrupadas para a fonte, não chamadas reais.

A política persiste cooldown e o cliente interrompe novas pessoas após 403/429/5xx. Na fotografia consultada, o cooldown persistido da Câmara já estava vencido; o último código gravado era o erro de esquema, pois o registro de política conserva o primeiro erro do grupo. O 429 é incidente comprovado, mas não prova indisponibilidade atual da fonte. Retomar em lotes menores, respeitar `Retry-After`, cache e campos pedidos. Uma tentativa bloqueada não fornece salário nem autoria e não pode resolver a lacuna.

### Descoberta de folha ALESP: `NO_PUBLISHED_PAYROLL_RESOURCES`

O reprocessamento remoto registrou esse erro; na consulta atual, 18.956 tarefas em 4.784 pessoas carregam o código e o cooldown da ALESP está ativo. Novamente, o código foi propagado por fonte: não prova uma tentativa individual em cada pessoa.

`discover_resources` produz esse erro quando não sobra recurso após reconhecer links e aplicar filtros. Os relatórios disponíveis **não distinguem ausência real de publicação, mudança do índice ou filtro sem correspondência**. Não é possível afirmar qual dessas causas ocorreu sem examinar o índice original e a configuração exata do lote. Há 100 pendências salariais `outdated`; folhas até agosto/2026 não satisfazem o critério de setembro/2026 na data auditada.

Ação: comparar catálogo original salvo, links reconhecidos, ano/mês configurados e último mês efetivamente publicado; ajustar parser apenas com evidência de formato. Até isso ocorrer, não chamar a folha histórica de salário atual nem preencher com o subsídio legal previsto.

### Identidade ou exercício não confirmado

Código `INSTITUTIONAL_IDENTITY_OR_CURRENT_ROLE_NOT_CONFIRMED`: 297 tarefas da Câmara bloqueadas em 99 pessoas, mais 99 tarefas de partido dessas mesmas pessoas redirecionadas para `tse_filiation` e ainda enfileiradas.

O retorno sem correspondência não permite distinguir automaticamente nome público divergente, pessoa fora do roster atual, identidade insuficiente ou ausência de mandato. O código agrega essas possibilidades; não há evidência para classificar todas como homônimos ou como não eleitas.

Ação: revisar nomes civis e públicos, nascimento e documento válidos; consultar fonte compatível com o vínculo e sua vigência. Não aproximar nomes para ligar pagamentos. Ausência em uma casa não prova ausência de todos os cargos públicos; a flag deve permanecer desconhecida até evidência suficiente.

### Campos ainda não suportados

`SOURCE_FIELD_NOT_SUPPORTED` aparece em duas tarefas ALERJ de uma pessoa: cargo atual e atividade política. O conector coleta partido e pagamento, mas normaliza `inExercise=None` e não produz mandato/exercício comprovado. Desenvolver aquisição de atos/períodos de exercício e autoria; pagamento isolado não autoriza inventar o mandato.

O mesmo código aparece em duas tarefas do Senado de uma pessoa: salário e atividade política. O conector atual fornece perfil, partido e exercício, mas não tem parser validado de folha mensal nem autoria. Implementar esses domínios; valor legal do subsídio não equivale a pagamento recebido.

Essas quatro tarefas são bloqueios já observados, não a quantidade total de pessoas que poderão precisar dos novos campos. Outros lotes ainda não foram executados.

### Fonte nominal de filiação não validada

`tse_filiation` retorna `PUBLIC_NOMINAL_AFFILIATION_SOURCE_NOT_VALIDATED`, zero chamadas e zero fatos. É um contrato bloqueado de integração. Na consulta atual, as 99 tarefas já encaminhadas a ele ainda não foram processadas por esse contrato; por isso o código nominal de bloqueio não aparece nelas ainda.

Ação: validar recurso oficial nominal, acesso permitido, chave pessoal, periodicidade e significado das datas antes de implementar coleta. Delegados partidários não representam todos os filiados. Datas de observação institucional/eleitoral não comprovam entrada ou saída real; não podem encerrar artificialmente um período de filiação.

### Declarações e dados pessoais TSE

A fila global mantém 710 ausências e 31 conflitos patrimoniais por campo. `DECLARATION_CONFLICT_REQUIRES_REVIEW` significa declaração de inexistência de bens e itens existentes para a mesma eleição. O serviço identifica o conflito; não decide qual versão é verdadeira.

O lote TSE examinado selecionou 17 pessoas, terminou sem falhas/rejeições, mas não produziu fatos novos nem reparou campos pessoais. Isso não demonstra que todas as 710 ausências foram pesquisadas, nem que nenhum dado existe na origem. Seus conflitos retornados foram zero nesse recorte, sem invalidar os 31 conflitos globais.

Ação: agrupar ausência por eleição/UF/tipo, verificar arquivos locais e republicações e confirmar correspondência de eventos. Reconciliar conflitos preservando ambas as evidências. Para os dois nascimentos e duas escolaridades ausentes, verificar fato original e unicidade antes de preencher. Sucesso técnico sem fato novo não sana pendência.

## Escopo insuficiente e não aplicabilidade

Os conectores cobrem fontes eleitorais e quatro casas legislativas; não cobrem universalmente executivos, municípios, carreiras administrativas ou benefícios previdenciários. Há candidatos históricos que podem nunca ter exercido mandato ou já ter saído dele. A contagem exata dessas situações não foi comprovada nesta auditoria.

Atividade política neste serviço significa existência de autoria parlamentar vinculada; a falta dessa autoria não comprova falta de atuação política. Ampliar a taxonomia de eventos e fontes antes de tratar todas essas ausências como erro do crawler.

`has_current_public_office=false` exige evidência negativa expressa, válida e de escopo suficiente; somente então salário atual pode ser `not_applicable`. Na fotografia global, 93 pessoas têm flag positiva e 15.355 estão desconhecidas; nenhuma tem negativa confirmada. Não forçar `false` para liberar fila. Atraso de publicação pode justificar tratamento operacional, mas não produzir pagamento fictício.

## Evidências e próximos passos

Fontes locais consultadas: `data/enrichment/production-dispatch-result.json`, `production-alesp-retry-result.json`, `production-local-activity-result.json`, `production-alerj-reference-result.json`, `production-senado-reference-result.json` e `data/private/final-orchestration-audit.json`. São relatórios privados; resultados de execuções de uma pessoa não devem ser publicados como cobertura global. Nenhuma identidade individual desses relatórios é reproduzida aqui.

A consulta somente de leitura agrupou `person_data_gap` por fonte/status/erro e campo/qualidade, contou tentativas e consultou `source_request_policy`. A fotografia global tem 301 tarefas bloqueadas e 62.783 enfileiradas. Nenhuma estava marcada como processada. Contagens de erro propagado são indicadores de política da fonte, não estatísticas de incidentes por pessoa.

Prioridades: comprovar a retomada das correções; diagnosticar a descoberta da folha ALESP; executar os lotes ainda não tentados com orçamento e cooldown; completar os domínios ALERJ/Senado; validar fonte nominal de filiação; reconciliar conflitos TSE; ampliar a classificação de aplicabilidade e o escopo de cargos. A flag de processamento só muda após reavaliação das evidências, e apenas então a pendência pode ser expurgada.
