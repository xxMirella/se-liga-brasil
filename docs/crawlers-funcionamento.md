# Crawlers: funcionamento, cobertura e localização dos dados

Auditoria do código em 17/10/2026. Este documento descreve o comportamento implementado; disponibilidade de um endpoint não significa que todos os seus dados já estejam ingeridos. Todos os nomes de tabelas abaixo pertencem ao schema privado `se_liga_brasil`.

## Como consultar pagamentos de qualquer pessoa

Os valores são colunas materiais de `person_payroll_payment`, relacionadas por `person_id`. A consulta não lê arquivos nem exige junção de proveniência. Deixe os dois filtros nulos para uma consulta geral, preencha `person_id` com o UUID interno para uma pessoa ou `name_query` com o texto pesquisado. O limite de 200 é uma proteção desta consulta administrativa, não paginação da API pública.

```sql
WITH filters AS (
    SELECT NULL::uuid AS person_id, NULL::text AS name_query
)
SELECT
    p.id AS person_id,
    p.display_name,
    p.has_current_public_office,
    p.current_public_office_kind,
    payment.organization_code,
    payment.competence,
    payment.gross_amount,
    payment.tax_amount AS deductions_amount,
    payment.net_amount
FROM se_liga_brasil.person p
CROSS JOIN filters f
LEFT JOIN se_liga_brasil.person_payroll_payment payment
    ON payment.person_id = p.id AND payment.identity_status = 'verified'
WHERE (f.person_id IS NULL OR p.id = f.person_id)
  AND (f.name_query IS NULL OR p.display_name ILIKE '%' || f.name_query || '%')
ORDER BY p.display_name, p.id, payment.competence DESC NULLS LAST
LIMIT 200;
```

Consulta também disponível em `db/queries/person_payments.sql`. Cada linha é um pagamento por órgão, cargo, tipo de folha e competência; não some bruto com líquido nem pagamentos de meses diferentes. Pessoas sem pagamento verificado continuam no resultado com valores nulos; desconhecido não vira zero. A coluna legada `tax_amount` representa o agregado de deduções da fonte, não apenas imposto de renda. A consulta de histórico não promete que a última competência publicada seja a competência vigente.

## Contrato comum dos crawlers

Os crawlers recebem o escopo da coleta; quem identifica lacunas é o serviço de completude. O orquestrador lê `person_data_gap`, agrupa campos por fonte e `person_id`, assume tarefas com lease e `FOR UPDATE SKIP LOCKED`, chama o coletor e reavalia os fatos depois da ingestão. O teto padrão é 1.000 tarefas por despacho, não 1.000 requisições.

Identidade de pessoa é sempre o UUID interno `person.id`. CPF válido é comparado por impressão HMAC em `person_document_identity`; a alternativa exige nome civil completo e data de nascimento completa com associação única. Nomes públicos ajudam a selecionar perfis para investigar, mas não autorizam sozinhos o vínculo final. Ambiguidade ou conflito gera revisão; não cria vínculo aproximado silencioso. Códigos externos de parlamentar/candidato são usados para navegar endpoints e relacionar eventos/arquivos da própria fonte, não como identidade permanente de pessoa.

Arquivos baixados são originais imutáveis. Novas respostas recebem novos caminhos/checksums; normalização gera arquivos derivados. Cada registro conserva URL, hash, instante de coleta, payload e referência ao arquivo. A reconciliação compara fonte/tipo/chave/conteúdo e versão do parser; repetir o mesmo conteúdo validado não duplica o fato. Alterações geram versão de entidade e evidência próprias. Reprocessar pode atualizar projeções sem baixar novamente.

A aquisição compartilhada restringe hosts oficiais, tamanho por arquivo/execução, timeout e tentativas. Há espaçamento por host, cache/checksum e janela padrão de rechecagem de 24 horas nos conectores institucionais. Respostas 403/429 suspendem a fonte; 5xx têm tentativas limitadas. `Retry-After` e `source_request_policy` impedem que outro despacho volte imediatamente à fonte bloqueada. Cache não impede que determinados índices sejam consultados de novo: a descoberta ALESP, por exemplo, consulta seu índice a cada execução de folha.

Tabelas comuns de controle/proveniência: `source`, `source_record`, `ingestion_run`, `ingestion_artifact`, `ingestion_entity`, `ingestion_entity_version`, `ingestion_artifact_entity` e `ingestion_rejection`. Registros recusados não devem ser tratados como fatos canônicos. `person_identity_review` registra conflitos de identidade. `person_data_gap` é fila temporária: `is_processed=true` somente após completude confirmar atendimento/justificativa; o expurgo remove resolvidas em lotes. Falha de tentativa continua pendente. O histórico de fatos permanece nas tabelas próprias, não na fila.

## TSE — `src/crawlers/tse/`

### O que busca

Candidaturas e histórico eleitoral, nome civil/público, nascimento, escolaridade, ocupação declarada, partido no contexto eleitoral, situação/resultado da candidatura, declarações de bens, planos de governo e certidões criminais quando publicados e selecionados na configuração. Ocupação declarada não comprova cargo atual nem aposentadoria atual. O TSE não fornece neste fluxo salário recebido ou remuneração parlamentar.

### Como busca e relaciona

Descobre conjuntos no catálogo CKAN `https://dadosabertos.tse.jus.br/api/3/action/`, usando `package_search` e `package_show`; aceita arquivos somente de `dadosabertos.tse.jus.br` e `cdn.tse.jus.br`. Filtra ano, UF, cargo e tipo. Faz download de ZIP, lê entradas em streaming com limites de expansão, normaliza CSVs e guarda documentos publicados sem modificar os originais. O padrão suporta arquivos de até 1 GiB, 10 GiB por execução, entrada expandida de até 512 MiB e 4 GiB expandidos por arquivo.

A ingestão principal resolve candidatos por CPF validado/HMAC ou nome+nascimento único. A sequência de candidatura só relaciona bens/documentos com o evento eleitoral já resolvido. A projeção mantém o mesmo `person_id` entre eleições.

O enriquecimento delegado `collect_requested_tse_data` agrupa pessoas/anos/campos, reaproveita downloads locais de `data/tse` e descobre/baixa apenas combinações ano/tipo ausentes. Para campos pessoais seleciona `candidate`; para bens/patrimônio seleciona `asset`. Usa índice SQLite temporário para limitar candidaturas/identidades solicitadas, não uma requisição por candidato. A configuração desse enriquecimento restringe UF a SP/RJ. Também pode preencher nascimento/escolaridade nulos a partir de fatos TSE já ingeridos; nascimento com versões conflitantes não é escolhido arbitrariamente.

### Tabelas preenchidas

- `person`: criação/resolução de pessoa, nomes, nascimento, escolaridade e demais campos pessoais previstos na projeção; atualizações respeitam evidência e contexto temporal.
- `person_document_identity`: tipo e impressão do documento, ligados ao UUID e à evidência. Não é armazenamento do CPF em claro como chave de outra fonte.
- `electoral_candidacy`: pessoa, ano, sequência técnica, turno, UF, cargo disputado, situação, resultado e referências ao partido/observação.
- `political_party`: código, nome, sigla e última observação eleitoral.
- `political_party_affiliation`: observação eleitoral por pessoa/partido/fonte, `information_scope='electoral:<ano>'`, validade da informação e evidência.
- `person_fact`: fatos normalizados e valores originais com evidência.
- `candidate_asset_declaration`: pessoa, ano, ordem/tipo/descrição, `declared_value`, `value_quality_status` e fonte. Valores negativos são preservados e sinalizados; não convertidos para zero.
- `candidate_document`: tipo, ano, caminho/hash do plano de governo ou certidão.
- `person_activity_context`: contexto de atividade/evento da fonte; não equivale a autoria parlamentar.
- `person_identity_review` e `ingestion_rejection`: pendências de validação/identidade.

### Limites e estado

Crawler e ingestão principal operacionais; ampliação de campos pessoais implementada no enriquecimento delegado. A validação exige versão compatível do parser: manifestos antigos precisam ser revalidados, não apenas reenviados à ingestão. Declaração eleitoral não equivale a patrimônio atual verificado. A soma de bens de um ano não deve misturar eleições. Divergência entre declaração de inexistência de bens e itens de bens é retornada como `DECLARATION_CONFLICT_REQUIRES_REVIEW`; a função apenas detecta o conflito, não o resolve. Partido de candidatura não é automaticamente partido atual. Datas de observação não provam datas reais de entrada/saída do partido.

## ALESP — `src/crawlers/alesp/`

### O que busca e como

O fluxo remoto principal coleta folhas de deputados estaduais de SP. Descobre meses efetivamente publicados no índice `https://www.al.sp.gov.br/alesp/folha-de-pagamento-deputados/`; aceita links `/repositorio/folha-de-pagamento/folha-deputados-AAAA-MM.html`, respeitando anos/meses configurados. Lê a tabela HTML, normaliza nomes e valores, conserva competência, componentes e evidência. Limites padrão: 10 MiB por arquivo, 100 MiB por execução, timeout de 60 segundos, três tentativas e lotes de 500.

Para identidade usa o cadastro `https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml`, perfis `https://legis-api-portal-prd.al.sp.gov.br/parlamentar-portal/detalhes/<código>` e páginas de telefone/perfil oficiais quando necessárias. Revisões explícitas ficam em arquivo derivado de resolução; colisões ou nomes insuficientes não autorizam vínculo com a pessoa. Uma linha pode permanecer sem vínculo verificado até revisão. A projeção atual de folha consulta `person_identifier` no namespace `payroll_recipient`: a chave é um hash interno do nome normalizado da folha, criado/revisado pelo resolvedor, não o código de deputado da ALESP. Essa tabela técnica auxilia a ligação da folha ao UUID; não é uma segunda identidade de pessoa.

O enriquecimento local reaproveita `identity-resolution.json` e arquivos verificados por checksum. Partido e cargo vêm de perfis institucionais; mandatos conservam o período da legislatura, sem inventar início individual de exercício. Para autoria combina `61_deputados.xml`, `81_documento_autor.zip` e `56_proposituras.zip` já presentes em `research/datasets`, vinculando autores somente às identidades revisadas. Usa SQLite temporário indexado para relacionar documento/autor durante a leitura em streaming. Esse caminho local não consulta a rede. O coletor delegado só executa o fluxo de folha quando salário foi solicitado.

### Tabelas preenchidas

- `person_payroll_payment`: competência, organização `alesp`, cargo `state_deputy`, bruto/deduções/líquido, nome do beneficiário, status da identidade, pessoa quando verificada e `source_record_id`.
- `institution`: instituição ALESP.
- `person_fact`: `alesp_institutional_profile`, `current_public_office_observation` quando o perfil contém estado booleano de exercício, e fatos do contexto da ingestão.
- `political_party_affiliation`: partido observado, escopo `institution:alesp`, período de validade da informação e fonte.
- `office_term`: legislatura, pessoa, instituição, cargo, UF, período e fonte. O período não cria sozinho uma linha em `office_exercise` neste conector.
- `proposition`: chave técnica do documento, natureza, número, ano, ementa e instituição.
- `proposition_person`: vínculo da proposição com a pessoa, `role='author'`, e evidência.
- `person`: snapshot de cargo atual atualizado pelo projetor compartilhado a partir de observação válida.

### Limites e estado

Folha operacional: ingestão já confirmada de 1.039 pagamentos de 100 pessoas, entre outubro/2025 e agosto/2026. Isso não representa cobertura de pensionistas/aposentados nem de todos os servidores. Enriquecimento local de partido/cargo/autoria implementado; resultados de cada execução devem ser conferidos no relatório, sem presumir que todo autor do acervo tem identidade resolvida. O catálogo local contém grande acervo, mas tamanho do arquivo não é quantidade de fatos ligados às pessoas. Autoria não comprova aprovação, relatoria, voto ou impacto. Filiações presentes no payload não são automaticamente uma cronologia canônica completa de entrada/saída.

## Câmara — `src/crawlers/camara/`

### O que busca e como

Usa `https://dadosabertos.camara.leg.br/api/v2/`: lista deputados por UF, detalhe `deputados/<id>`, `deputados/<id>/historico`, `legislaturas/<id>` e `proposicoes?idDeputadoAutor=<id>&itens=100&ordem=ASC&ordenarPor=id`. Lista é compartilhada por UF; detalhe é comparado com a pessoa antes da ingestão. O perfil usa CPF válido ou nome civil+nascimento único; ID do deputado serve para navegação.

Salário vem do HTML `https://www.camara.leg.br/deputados/<id>/remuneracao?ano=<ano atual>`; seleciona o último mês publicado e busca `/remuneracao-deputado-detalhado?mesAno=MMAAAA`. Valida pessoa, competência e folha normal, reconcilia com Decimal proventos/deduções/líquido e conserva auxílios/diárias separados. Histórico é filtrado à legislatura efetiva, evitando tratar indicação de legislatura futura como exercício atual.

Paginação segue links oficiais com limite de 100 páginas e detecção de ciclos. Limites padrão: 25 pessoas por execução do conector, 20 MiB por arquivo, 200 MiB por execução, timeout 60 segundos e três tentativas. O coletor atual executa perfil, salário e autoria para cada pessoa selecionada; ainda não separa a atualização remota por campo solicitado. Rechecagem recente evita repetição completa dentro da janela operacional.

### Tabelas preenchidas

- `institution`: Câmara.
- `person_fact`: perfil/pagamento/autoria com evidência administrativa verificada.
- `person`: nascimento/escolaridade somente quando faltantes, foto quando publicada e snapshot do cargo atual.
- `political_party_affiliation`: observação institucional `institution:camara` e validade da informação.
- `office_term`: mandato/legislatura da pessoa e período.
- `office_exercise`: início explícito, capacidade titular/suplente e encerramento somente com evidência explícita; ausência no retorno não prova saída.
- `person_payroll_payment`: organização `camara`, `federal_deputy`, competência, folha normal, bruto, deduções, líquido e identidade verificada.
- `proposition` e `proposition_person`: proposição e autoria ligada à pessoa. Ano desconhecido é NULL; situação não é inventada.

### Estado e limites

Operacional, com ingestão verificada e consulta geral acima. Não coleta neste fluxo votos, relatorias, resultado legislativo detalhado ou avaliação de impacto. Não coleta aposentadoria/pensão. A existência de partido no histórico institucional não substitui histórico nominal completo de filiação.

## ALERJ — `src/crawlers/alerj/`

### O que busca e como

Lista deputados em `https://www.alerj.rj.gov.br/Deputados/QuemSao`, segue perfis oficiais e descobre a última folha no índice `https://transparencia.alerj.rj.gov.br/section/report/73`. Baixa PDF uma vez para o grupo, extrai texto com `pdftotext -layout` e seleciona somente linhas `DEPUTADO ESTADUAL`. Não é um parser genérico de todas as folhas da ALERJ.

Exige 16 colunas e competência explícita no cabeçalho. Soma sete componentes de proventos e cinco deduções, reconciliando com líquido; indenização fica separada. Nome completo da folha mais nascimento do perfil são comparados à pessoa pelo resolvedor comum. Apelido no roster somente localiza perfil; homônimos/ausência de nascimento não produzem vínculo automático. Evidência do perfil é um bundle do perfil, folha e roster, com hashes.

Limites padrão: 25 pessoas, 40 MiB por arquivo, 100 MiB por execução, timeout 60 segundos, três tentativas, lotes de 500 e cache 24 horas. Requer `pdftotext` instalado; ausência gera erro explícito.

### Tabelas preenchidas

`institution`, `person_fact`, `political_party_affiliation` com escopo `institution:alerj`, `person_payroll_payment` (`organization_code='alerj'`, competência/bruto/deduções/líquido/identidade), além de nascimento nulo em `person` quando verificado. O projetor chama a atualização compartilhada de cargo, mas o perfil atual normaliza `inExercise=None`: não fornece comprovação de exercício e não cria `office_term`/`office_exercise`.

### Estado e limites

Conector implementado para partido e salário. Ingestão de produção deve ser comprovada pelo relatório de execução; não é afirmada aqui para todas as pessoas. Campos `current_public_office` e `political_activity` são declarados não suportados. Não converte inclusão no roster em exercício confirmado. Não coleta benefícios previdenciários nem história completa de filiação.

## Senado — `src/crawlers/senado/`

### O que busca e como

Usa `https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json` uma vez para o grupo e `senador/<código>.json` para detalhes. Indexa nomes civis completos para localizar parlamentar único e compara nome+nascimento com o UUID solicitado antes de projetar. Normaliza partido, UF, legislatura, mandato e períodos de exercício disponíveis. Datas finais são normalizadas como limite exclusivo.

Limites padrão: 25 pessoas, 20 MiB por arquivo, 100 MiB por execução, timeout 60 segundos, três tentativas, lotes de 500 e cache 24 horas. Falhas 403/429/5xx interrompem novas pessoas naquela coleta. Pessoas sem correspondência e excedentes são explicitamente devolvidos ao orquestrador.

### Tabelas preenchidas e limites

`institution`, `person_fact`, `political_party_affiliation` no escopo `institution:senado`, `office_term`, `office_exercise` quando houver início explícito e exercício confirmado, e snapshot de cargo em `person`. Conector implementado para partido/cargo. Não tem parser de folha mensal real e não grava `person_payroll_payment`; salário e atividade legislativa são campos não suportados. Subsídio legal previsto não substitui pagamento recebido. Uma referência verificada teve perfil, partido, mandato e exercício materializados em produção; salário e atividade permaneceram bloqueados por falta de coletor validado. Isso não comprova cobertura de todas as pessoas.

## Filiação nominal TSE — `src/crawlers/tse_filiation/`

É um contrato de integração bloqueado, não um crawler nominal operacional. Recebe pessoas/campos e retorna `PUBLIC_NOMINAL_AFFILIATION_SOURCE_NOT_VALIDATED`, zero requisições, zero fatos ingeridos e referências para validar a fonte pública. Escopo pretendido: partido atual e histórico de filiação. O catálogo de delegados partidários não comprova filiação de todos os candidatos.

Não preenche tabelas canônicas. O orquestrador mantém a lacuna bloqueada com motivo, evitando uma requisição falha por pessoa. Não existe neste módulo obtenção comprovada de datas de entrada/saída. A validade da informação armazenada nas observações institucionais/eleitorais é distinta da data real de filiação/desfiliação. `information_valid_from`/`information_valid_until` versionam a informação observada por escopo; não constituem, por si só, SCD tipo 2 completo da permanência efetiva nos partidos.

## Cargo atual na tabela `person`

A migração `0013_person_current_public_office.sql` adiciona `has_current_public_office`, `current_public_office_kind`, `current_public_office_institution_id`, `current_public_office_term_id`, `public_office_status_as_of` e `public_office_status_source_record_id`.

- `true`: exercício atual confirmado por evidência administrativa válida, com cargo, instituição e fonte.
- `false`: ausência expressamente comprovada de cargo público, com escopo `all_public_offices` e vigência. Não é inferida de candidatura perdida ou ausência em uma casa legislativa.
- `NULL`: situação desconhecida, evidência vencida ou contraditória. Não tratar como `false`.

O SQL compartilhado `db/ingestion/person_current_public_office.sql` combina `office_term`/`office_exercise` e fatos `current_public_office_observation`, usando evidências recentes de até 30 dias. Confirmação negativa exige fato `public_office_status` verificado com prazo de validade. Evidências positiva e negativa conflitantes deixam o snapshot desconhecido. Câmara, ALESP e Senado podem fornecer evidência positiva; ALERJ ainda não. Nenhum crawler atual cobre universalmente ausência de todos os cargos públicos. Se houver mais de um exercício confirmado, o snapshot escolhe a evidência mais recente; os vínculos individuais continuam nas tabelas de mandato/exercício.

```sql
SELECT p.id, p.display_name, p.has_current_public_office,
       p.current_public_office_kind, i.name AS institution,
       p.current_public_office_term_id, p.public_office_status_as_of,
       p.public_office_status_source_record_id
FROM se_liga_brasil.person p
LEFT JOIN se_liga_brasil.institution i ON i.id=p.current_public_office_institution_id
ORDER BY p.display_name, p.id LIMIT 200;
```

## Cobertura que permanece aberta

Completude verifica nome, nascimento, escolaridade, partido atual, salário atual, bens/patrimônio eleitoral e cargo atual; também diagnostica autoria política. Benefícios de aposentadoria/pensão ainda não integram esses campos mínimos. Para salário, espera competência do mês anterior ou mais recente; atraso de publicação pode manter lacuna mesmo com folha histórica válida. Com ausência universal de cargo confirmada, salário de cargo atual é `not_applicable`, sem fabricar valor zero.

Portais estaduais/federais de transparência e cadastro PEP/CGU são linhas de pesquisa para vínculos, benefícios e cruzamento. Não há aqui crawler PEP/CGU implementado ou garantia de chave comum disponível. Tampouco há conectores de executivos, municípios, carreiras administrativas ou benefícios capazes de cobrir toda pessoa historicamente candidata. Essas lacunas devem permanecer explícitas, sem encaminhamento repetido a uma casa legislativa que não cobre a pessoa.

## Como verificar execução e rastreabilidade

O CLI oferece `audit-completeness` para diagnosticar, `enrich` para diagnosticar e delegar, `dispatch` para executar fila já persistida e `purge-gaps` para expurgar resolvidas. Os relatórios privados em `data/enrichment` e `ingestion_run` registram conclusão parcial/falhas. Um despacho sem tarefas vencidas não significa base completa: tarefas podem estar em cooldown, bloqueadas ou sem coletor.

Conferir fatos canônicos e evidências depois da execução, não apenas status HTTP. Chaves de fonte permanecem em eventos técnicos e arquivos originais, enquanto vínculos entre pagamentos, mandatos, bens e autoria utilizam o mesmo `person_id`. RLS e schema privado podem impedir visualização pelo cliente público; usar conexão autorizada e selecionar o schema correto.


## Execução real e correções de lote em 17/10/2026

O orquestrador foi executado para 1.000 pendências, agrupadas em 109 pessoas ALESP, 134 Câmara e 17 TSE. O lote foi parcial: a Câmara recebeu HTTP 429 e entrou em cooldown; um parecer sem número expôs campo opcional; coautorias ALESP expuseram deduplicação necessária na projeção de proposições. As correções mantêm autores distintos e uma única proposição por órgão/chave. A migração 0015 permite número desconhecido nulo, sem gerar número fictício ou descartar a autoria. Esses incidentes não apagam pagamentos já ingeridos. Resultados detalhados ficam em `data/enrichment/production-dispatch-result.json`.

Antes desse lote, 89 perfis ALESP foram materializados com zero HTTP, resolvendo e expurgando 178 pendências. O primeiro lote resolveu mais seis e deixou 63.090 pendências abertas nessa fotografia; não representa completude global. Nenhuma consulta de pagamento precisa abrir `storage_reference`.


### Execução por campo e independência da fonte remota

`dispatch --fields political_activity` limita as tarefas aos campos indicados (separados por vírgula). A ALESP processa primeiro os artefatos locais; falha da folha é registrada separadamente e não desfaz os fatos locais já validados. Tarefas exclusivamente locais da ALESP podem avançar durante cooldown remoto se estiverem prontas; salário continua sujeito ao cooldown. Não há requisição remota para essa coleta local.


Na Câmara, o orquestrador agora passa os campos de cada pessoa: atualizar apenas salário não percorre proposições. O perfil continua necessário para verificar identidade; artefatos de perfil reutilizam cache. A regressão verifica que consulta exclusivamente salarial não dispara aquisição de autorias.


Para descobrir o órgão, o roteamento prioriza instituição já confirmada; depois usa eleição anterior com período esperado ainda vigente como pista, antes da candidatura mais recente. Essa pista só escolhe o crawler: não marca exercício nem preenche a flag. Foi encontrada uma referência com candidatura estadual em 2026 e eleição anterior para Senado; a pesquisa precisa consultar o Senado para confirmar a situação atual, e não assumir o cargo da candidatura futura.

Uma referência ALERJ foi identificada por nome civil completo e nascimento, com perfil/partido e pagamento inseridos, sem rejeições. Cargo atual e atividade permanecem não atendidos nessa fonte; o pagamento está em `person_payroll_payment`, sem depender de abrir PDF.


### Referência Senado verificada

Uma referência teve quatro tarefas delegadas ao Senado após corrigir a pista eleitoral: perfil/exercício e partido foram ingeridos, com zero rejeições; duas pendências foram resolvidas e expurgadas. Salário e atividade legislativa seguem bloqueados, sem gerar chamadas para campos não suportados. As referências ALERJ e Senado mantiveram os mesmos UUIDs pessoais.


## Fotografia final da retomada

Auditoria final em `data/private/final-orchestration-audit.json`: 15.448 pessoas preservadas; 93 com cargo confirmado (89 estaduais, três federais e uma senadora), 15.355 desconhecidas. Pagamentos materializados: ALESP 1.039, Câmara dois e ALERJ um. Vínculos de autoria: ALESP 708 e Câmara 1.871, sem equivalência com leis aprovadas. Restam 63.084 pendências; duas pessoas têm todos os campos mínimos atendidos. O backlog não foi integralmente resolvido.
