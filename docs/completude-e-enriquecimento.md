# Serviço de completude e enriquecimento

A responsabilidade de detectar lacunas pertence a `service/completeness`, não aos crawlers. O diagnóstico consulta todas as pessoas canônicas, inclusive pessoas sem candidatura. Os crawlers permanecem conectores de fonte: aquisição, normalização e validação.

Campos mínimos: nome completo, nascimento, escolaridade, partido institucional atual, último salário mensal, declaração de bens da última eleição, total patrimonial **declarado** nessa eleição e exercício atual de cargo público. Uma candidatura não prova cargo atual; declaração antiga de partido não comprova filiação atual. Patrimônio declarado não é patrimônio atual comprovado, nem deve ser somado entre eleições.

## Comandos

```bash
.venv/bin/se-liga-brasil audit-completeness --env-file /caminho/privado/.env
.venv/bin/se-liga-brasil enrich --person-id UUID_INTERNO --env-file /caminho/privado/.env
.venv/bin/se-liga-brasil enrich --env-file /caminho/privado/.env
```

O primeiro diagnostica sem ingerir. `enrich` busca dados nas fontes suportadas, relaciona-os à pessoa e reavalia os campos. Sem UUID, avalia a base e processa até 25 parlamentares federais por execução; a execução seguinte retoma pessoas sem consulta recente. Cache de 24 horas evita chamadas repetidas. Não foi criado agendamento automático. Pendências, pessoas não localizadas no catálogo atual e tarefas sem fonte mapeada não são classificadas como sucesso de cobertura.

Relatório global: `data/enrichment/completeness.json`; tarefas: `data/enrichment/collection-tasks.json`. Consulta individual: `data/enrichment/people/<UUID>/completeness.json`. Arquivos privados, com IDs internos e estados por campo. O enriquecimento individual não sobrescreve o relatório global. Estados implementados incluem presente, ausente, desatualizado, ausente/não verificado, declaração explícita sem bens e conflito. Não se usa zero para ausência nem “não aplicável” sem comprovação; “não publicado” na coleta é registrado no resultado, permanecendo como pendência no diagnóstico.

## Rotas e limites

- TSE: declarações eleitorais e bens. O serviço seleciona pessoas cuja última eleição não está coberta, cruza as linhas com candidaturas já identificadas e processa os arquivos por ano/lote. Reutiliza os originais baixados; descobre e baixa recursos faltantes. A chave de escopo inclui o conjunto de UUIDs para não pular novos alvos em uma reexecução.
- Câmara: partido institucional, mandato/exercício, salário e autoria federal. Nome no catálogo serve apenas para selecionar o perfil a conferir; a identidade exige CPF validado ou nome civil completo/nascimento único, compatível com o UUID esperado. Não cria outra pessoa, não salva ID parlamentar como identidade pessoal e não expõe CPF nos dados normalizados.
- ALESP: o planejador encaminha pendências estaduais à fonte. Havendo alvos com candidaturas estaduais, o serviço aciona uma coleta ALESP em lote, reutilizando o pipeline existente. Isso não garante cargo/partido atual para toda pessoa histórica: lacunas não cobertas pela fonte permanecem explícitas. Fontes municipais e outras instituições também exigem conectores próprios; uma candidatura federal/estadual é contexto de procura, não prova de mandato atual.

Atualidade inicial: partido institucional observado nos últimos 30 dias e pagamento da competência anterior ou mais recente. São critérios operacionais configuráveis a evoluir por calendário da fonte; atraso de publicação permanece pendente/desatualizado. Pessoas sem cargo público não devem receber salário fictício: é necessário comprovar o contexto ou manter a pendência. RG não é inferido nem implementado sem emissor/UF e campos disponíveis.

## Contrato Câmara

Reutiliza `OfficialHttpClient`, downloader com orçamento/cache/arquivos imutáveis, `HtmlTableParser`, normalizadores escalares, staging com checksums, `IngestionRepository` e `SqlBatchWriter`. Páginas da API são paginadas com limite e detecção de ciclos. Perfil possui bundle de referências dos arquivos de perfil, histórico e legislatura, evitando perder alterações de uma dependência quando o perfil sozinho não muda.

A remuneração vem da folha detalhada da pessoa e competência, não da cota parlamentar ou do gabinete. Soma as seções remuneratórias 1–3, reconcilia descontos obrigatórios da seção 4 com o líquido publicado da seção 5 e preserva auxílios/diárias da seção 6 separadamente no payload. A coluna legada `tax_amount` representa aqui o agregado de descontos obrigatórios, incluindo contribuição previdenciária; `deductionScope` documenta essa diferença. O líquido armazenado não é anunciado como total de todos os créditos.

Autoria vem do filtro oficial `idDeputadoAutor`, incluindo assinaturas e coautorias reconhecidas pela fonte. Não se atribui autoria exclusiva nem aprovação, sanção ou impacto: `current_status=unknown` até haver comprovação específica. Votos, relatorias e leis ainda não são coletados por este conector. Documentos com ano zero/ausente têm ano normalizado NULL; a fonte original é preservada, sem inferir ano pelo protocolo. A migração 0009 permite esse caso sem alterar registros existentes.

O perfil institucional é preservado como fato; dados civis já existentes não são sobrescritos para eliminar divergências. Nascimento/escolaridade vazios podem ser preenchidos a partir da evidência confirmada. Mandato e exercício possuem fonte própria; fechamento de exercício exige transição explícita datada, nunca ausência em arquivo.

## Verificação de execução

Foram verificadas associação pessoal, projeção de perfil/partido/exercício, remuneração mensal e autoria legislativa nas fontes suportadas. Resultados agregados estão nos relatórios privados de auditoria. A cobertura de referências individuais não demonstra completude global. A consulta geral de pagamentos está em `db/queries/person_payments.sql`.

## Fila persistente e responsabilidades

A fonte de verdade das pendências é agora `se_liga_brasil.person_data_gap` (migração 0010), não os JSONs. O serviço `service/completeness/assessment.py` somente avalia e salva. O serviço `service/orchestration/data_collection.py` atribui fontes, reserva tarefas, agrupa solicitações e aciona os conectores.

Cada linha contém UUID da pessoa, campo, estado da qualidade, fonte atribuída, estado da tarefa (`queued`, `running`, `resolved`, `blocked`), primeira detecção, última avaliação, próxima tentativa, quantidade de tentativas, erro e reserva temporária do trabalhador. A restrição única `(person_id, field_name)` impede duplicar pendências em auditorias repetidas. A flag `is_processed` começa falsa e só fica verdadeira, com `processed_at`, quando a completude confirma que o campo foi atendido. Tentativas falhas continuam pendentes. O expurgo automático após a avaliação e antes da delegação remove as linhas resolvidas em lotes de 1.000, até 10 lotes por execução, sem apagar pessoas, fatos ou evidências. Não mantemos histórico das pendências expurgadas; se o dado voltar a faltar, nasce uma nova pendência. A limpeza também pode ser executada com `se-liga-brasil purge-gaps --env-file CAMINHO_DO_ENV`. Pessoas sem fonte mapeada permanecem bloqueadas com motivo explícito.

O orquestrador usa `FOR UPDATE SKIP LOCKED`, reserva de 30 minutos e lote inicial de até 1.000 pendências. Vários campos de uma pessoa viram uma única solicitação à fonte. Bens são agrupados por ano; ALESP é coletada uma vez por lote; Câmara compartilha catálogo, perfis, legislatura, paginação e cache. Os locks de ingestão por fonte impedem coletores concorrentes da mesma fonte no banco. A identificação da fonte por candidatura serve apenas como encaminhamento; a fonte deve confirmar identidade e exercício.

Proteções contra excesso de requisições: espaçamento mínimo padrão de 1 segundo por domínio no processo, cache de 24 horas, arquivos imutáveis, limites de páginas/bytes/pessoas, retries limitados com backoff e respeito ao `Retry-After`. Esperas pedidas acima de 60 segundos retornam à orquestração, sem tentar novamente antes do prazo. Falhas adiam as tarefas da fonte por pelo menos uma hora (ou pelo prazo maior informado). Pendências consultadas mas não resolvidas aguardam 24 horas; nova auditoria não zera o cooldown. Pessoas ainda não processadas por limite de lote retornam à fila sem esse atraso. Não se contornam CAPTCHA ou bloqueios.

Autoria política é diagnosticada também, além do mínimo cadastral. A presença de uma proposição não comprova aprovação/impacto; ausência de proposições não prova ausência de atuação. Os relatórios JSON permanecem como espelhos privados de auditoria.

`dispatch` é o comando do trabalhador: lê a fila já salva, sem refazer a auditoria inicial. Exemplo: `se-liga-brasil dispatch --person-id UUID_INTERNO --env-file /caminho/privado/.env`. `enrich` continua como conveniência para auditar e despachar na mesma execução. Sem tarefas devidas, o trabalhador termina sem acessar fontes; isso não declara que toda a base está completa.

A migração 0011 adiciona `source_request_policy`: cooldown persistente por fonte. Até pendências criadas depois de um bloqueio respeitam esse prazo. O transporte abre um circuito local em 403/429 e após esgotar retries de falhas do servidor; demais recursos desse domínio não geram novos pedidos durante o bloqueio. O coletor Câmara interrompe a lista de pessoas no primeiro bloqueio; tarefas adiadas por esse motivo não voltam imediatamente à fila.


## Atualização de 17/10/2026: cargo atual e novos coletores

A pessoa agora tem flag anulável e cargo atual com órgão, mandato opcional, data e evidência. Ver `pessoa-cargo-atual.md`. `false` exige ausência global comprovada; desconhecido permanece `NULL`. A completude aceita ausência confirmada de cargo e salário do cargo não aplicável, sem fabricar valor zero.

Orquestração integrada com TSE ampliado, ALESP local, ALERJ, Senado e contrato FILIA. As capacidades de ALERJ/Senado são parciais, descritas em `crawler-alerj.md` e `crawler-senado.md`. Campos sem coletor operacional ficam bloqueados com motivo e sem expurgo. A fila existente passou a distinguir RJ estadual (ALERJ) de SP (ALESP).

A pesquisa adicional de conexões entre portais está em `portais-conexao-dados.md`; PEP/CGU é proposta complementar validada em lote, não um crawler integrado nesta entrega. O levantamento `cobertura-crawlers-pendencias.md` descreve o diagnóstico anterior a esses ajustes e suas contagens históricas.


Execução seletiva: `dispatch --fields political_activity` permite materializar atividade local sem consultar folha. Reprocessamento local respeita identidade, escopo, checksums e deduplicação de coautorias. Pendências de salário não atravessam o cooldown remoto.

## Prioridade de fotos, cargos e remuneração

A auditoria inclui `photo_url`: uma foto ausente permanece pendente, mesmo com nome e nascimento preenchidos. Câmara e Senado obtêm imagens oficiais somente após confirmação da identidade. A coleção do Senado ainda não fornece pagamentos; solicitações de remuneração permanecem bloqueadas explicitamente, sem usar o subsídio legal como se fosse pagamento recebido.

A fila prioriza exercício atual confirmado, depois eleição cujo mandato esperado está em curso, seguida das demais pessoas. Resultado eleitoral é somente uma prioridade de pesquisa e não comprova posse ou exercício. Dentro dessa ordem, foto, cargo e salário têm precedência. Leases e cooldowns continuam obrigatórios.

Para processar as pendências dessas áreas com fontes específicas, reutilizando o diagnóstico persistido:

```sh
se-liga-brasil dispatch --fields photo_url,current_public_office,current_salary --sources camara,senado --env-file /caminho/privado/.env
```

O lote tem no máximo 1.000 pendências e cada coletor mantém seu orçamento de pessoas/requisições. O parâmetro `--sources` permite separar fontes indisponíveis sem perder suas pendências. A leitura e o planejamento são proporcionais ao número de registros; o agrupamento evita repetir a mesma coleta para campos da mesma pessoa.

O campo `current_office_started_on` acompanha a data individual de início do exercício atual. Cargo confirmado sem essa data permanece incompleto: o início da legislatura não supre a lacuna. No histórico da Câmara, alterações de partido/nome durante exercício contínuo não reiniciam essa data; licença e retorno explícitos delimitam um novo período. Históricos contraditórios não produzem uma data presumida.

A correção de início de exercício da Câmara pode ser reprocessada a partir de originais em cache, com transporte remoto desativado. O fato derivado `camara_exercise` possui recurso e rastreabilidade próprios; não substitui silenciosamente um perfil com timestamp conflitante. As versões antigas permanecem no histórico, enquanto a leitura usa a data de coleta da evidência original, e não o número sequencial do registro, para ordenar correções e afastamentos.

Observações simultâneas de filiação na Câmara são agrupadas por instante antes de calcular o próximo limite SCD. Isso mantém várias evidências do mesmo acontecimento sem criar intervalo de duração zero, recusado por `affiliation_information_period_check`. O processamento não desativa a constraint nem transforma ausência de informação em mudança de partido.

## Retomada de pagamentos em lotes pequenos

`dispatch --fields current_salary --sources camara --task-limit 10` assume até dez
pendências vencidas da fonte. O intervalo aceito de `--task-limit` é de 1 a 1.000;
o padrão continua 1.000. O limite conta pendências, não chamadas HTTP ou pagamentos
novos. Cada fonte mantém também seus limites próprios de pessoas e bytes.

A prioridade acompanha o lote até o coletor: exercício confirmado, pista eleitoral
vigente, demais pessoas; depois prioridade do campo, próxima tentativa e ID da tarefa.
A seleção com lease e `SKIP LOCKED` retorna explicitamente nessa ordem, e o serviço
reordena os candidatos pela primeira tarefa da pessoa. Ordenar o lote no banco e
reenviar candidatos por UUID descartava a prioridade antes da coleta. O índice em
memória para reordenar custa O(n+k) em tempo e O(n) em memória, com n candidatos e k
pessoas solicitadas; não adiciona chamadas remotas por pessoa.

HTTP 429 interrompe a fonte, conserva o cooldown persistido e mantém as pendências
sem fato correspondente. Um lote parcial pode ter gravado pagamentos válidos antes
do bloqueio; verificar o relatório e o banco antes de repetir. O comando é finito e
não instala um agendamento.

Verificação em 22/10/2026: a folha ALESP publicada mais recente no índice oficial
continua sendo agosto/2026. Os pagamentos existentes continuam visíveis no perfil,
mas não satisfazem a regra de competência atual de setembro/2026. Não confundir
pagamento desatualizado com ausência de qualquer pagamento.
