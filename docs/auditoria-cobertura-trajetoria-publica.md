# Auditoria da cobertura da trajetória pública

Verificação em 17/10/2026. Consultas ao PostgreSQL executadas em transações `READ ONLY`, além de revisão dos crawlers, projeções e serviços. Não houve ingestão, alteração dos arquivos originais ou implementação de novos serviços. O caso individual solicitado foi usado apenas para validação interna; este documento apresenta achados gerais.

## O que a base comprova hoje

A base contém **2.501 proposições**, todas com `current_status='unknown'`. As tabelas `proposition_event`, `voting`, `person_vote`, `law`, `proposition_law` e `public_career_event` estão vazias. Portanto, o sistema já relaciona pessoas a proposições, mas não consegue demonstrar quais foram aprovadas, rejeitadas, convertidas em lei ou como cada parlamentar votou. Zero registros nessas tabelas significa ausência de dados ingeridos, não ausência de atividade política.

Há apenas quatro registros globais de `person_data_coverage`: todos parciais e sem limites temporais preenchidos. Essa tabela existe, mas ainda não comprova períodos integralmente consultados. Datas mínima e máxima das proposições encontradas descrevem os registros existentes; não demonstram que todos os registros entre elas foram coletados.

O esquema consultado tem 39 tabelas, sem entidades específicas para empresas, participação societária ou instrumentos de parceria. Declarações de bens podem conter participações declaradas, mas não substituem cadastro empresarial, quadro societário ou histórico de administração.

O arquivo `db/schema.sql` é a definição inicial: a análise do banco deve considerar também as migrações. Por exemplo, ano e número de proposições tornaram-se opcionais em migrações posteriores. Não se deve interpretar a definição inicial isolada como estado atual da produção.

## Por que a completude atual não resolve o histórico

Nota de implementação posterior à leitura auditada: a regra de presença passou a classificar uma autoria isolada como `partial`, mantendo a lacuna aberta. O módulo `service/public_career_coverage` já possui planejamento por escopo e recibos explícitos; sua coleta, persistência de cobertura e integração ao despacho ainda estão em desenvolvimento. As contagens desta auditoria descrevem a leitura anterior, não uma nova ingestão.

`src/database/completeness.py` calcula `has_propositions` por `EXISTS` em `proposition_person`. Em `src/service/completeness/rules.py`, qualquer vínculo faz `political_activity` ficar `present`. O campo não integra os oito requisitos mínimos que determinam `complete`.

Isso é insuficiente para trajetória: uma única proposição antiga satisfaz a presença mesmo se faltarem legislaturas inteiras, atualizações recentes, resultados, votos e atuação municipal. O serviço atual não verifica cobertura por instituição, domínio e período.

O crawler Câmara consulta `/proposicoes` por autoria, com paginação, e declara explicitamente `authorship_only_approval_not_inferred`. Tanto `db/ingestion/camara_propositions.sql` quanto `db/ingestion/alesp_propositions.sql` gravam status `unknown` e papel `author`. Listagem por autoria não basta para classificar automaticamente autor principal versus coautor; é preciso coletar e preservar a informação de autores/papéis fornecida pela fonte. Os coletores examinados não preenchem tramitações, votação nominal nem vínculo com norma promulgada.

O perfil Câmara cria o mandato referente à legislatura do perfil e registra exercício quando há início individual comprovado. Isso não equivale a carregar toda a carreira nem mandatos municipais anteriores. O TSE fornece candidaturas; eleição ou candidatura não prova, por si só, posse e exercício.

## Semântica necessária

- **Proposição apresentada:** manter seu tipo. Requerimentos, destaques, pareceres e documentos não devem ser contados como projetos de lei.
- **Autoria/coautoria/relatoria:** vínculos distintos, com fonte; não derivar papel apenas da presença no mesmo resultado de busca.
- **Aprovação/rejeição:** registrar órgão, data, objeto e etapa. Aprovação em comissão ou de um requerimento acessório não significa aprovação final do projeto principal.
- **Lei:** exigir vínculo oficial entre proposição e norma, jurisdição, publicação e eventuais vetos. Lei resulta de processo coletivo, não de autoria exclusiva presumida.
- **Voto individual:** exigir registro nominal. Votação simbólica pode ter resultado coletivo sem voto individual publicado; não converter ausência de registro em voto contrário ou ausência à sessão.
- **Início da vida pública:** apresentar primeiro fato conhecido e sua cobertura. A primeira candidatura na base não comprova o início real da atuação pública, que pode anteceder eleições ou cargos.
- **Empresa:** separar participação declarada em bens, participação societária cadastral e administração. Correspondência de nome ou CPF parcialmente mascarado gera candidato à identificação; não confirmação automática.
- **Parceria:** identificar instrumento, partes, papel, objeto, vigência e evidência. Coautoria é colaboração legislativa; reunião ou fotografia não comprova sociedade nem parceria formal. Emenda ou transferência também não torna o parlamentar executor do projeto.

## Fontes e coletores que faltam

1. **Ampliar o crawler Câmara:** detalhes das proposições, autores/papéis, tramitações, relações entre proposições, votações, votos nominais e ligação comprovada com leis. Priorizar arquivos oficiais por ano, quando disponíveis, compartilhados entre pessoas; usar endpoints específicos para complementos e alterações. A [documentação oficial da API e arquivos](https://dadosabertos.camara.leg.br/swagger/api.html?tab=api) descreve autores e recursos legislativos. O [guia de votações](https://dadosabertos.camara.leg.br/howtouse/2020-02-07-dados-votacoes.html) esclarece objetos acessórios e os conjuntos separados de votações e votos individuais.

2. **Criar crawler Câmara Municipal de São Paulo:** trajetória municipal, vereança, projetos, deliberações e votações. O [catálogo de dados abertos](https://www.saopaulo.sp.leg.br/transparencia/dados-abertos/dados-disponibilizados-em-formato-aberto/) disponibiliza SPLEGIS, exportações e acervo legado. A [base de projetos](https://www.saopaulo.sp.leg.br/documentacao/pesquisa/projetos/) informa registros desde 1948, pesquisa por autor, deliberação e norma correspondente; cobertura de texto integral varia por período. O [web service SPLEGIS](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx) expõe métodos de projetos e deliberações. Validar contratos, paginação, abrangência histórica e papéis antes de prometer completude.

3. **Ampliar ALESP, ALERJ e Senado por domínio:** os coletores atuais não oferecem cadeia completa de resultados, leis e votos. ALESP tem autoria local; ALERJ e Senado têm coleta de perfil/mandato ou remuneração conforme documentação do projeto. A ampliação deve ser por instituição e período; não enviar histórico municipal à assembleia estadual apenas por coincidência de UF. Outras câmaras municipais serão necessárias conforme os mandatos efetivamente encontrados.

4. **Histórico eleitoral e mandatos:** reutilizar TSE por eleição/UF e arquivos já baixados, verificando todas as candidaturas identificadas, resultados e lacunas de anos. Acrescentar fontes institucionais de posse, afastamento, renúncia e retorno. Não assumir que todos os anos anteriores são aplicáveis nem fabricar um mandato a partir do resultado eleitoral.

5. **Empresas:** criar coletor da Receita Federal/CNPJ, com processamento local seletivo dos arquivos e estratégia de identificação revisada. O [layout oficial do CNPJ](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf/@@download/file) distingue empresas, estabelecimentos e sócios, e prevê descaracterização de CPF nos dados abertos. O snapshot atual não recupera automaticamente todas as saídas societárias do passado; datas de entrada, observação e eventual saída comprovada precisam permanecer diferentes. Não há esse coletor/modelo operacional hoje.

6. **Parcerias e execução de recursos:** validar coletores de emendas/transparência e [APIs oficiais do Transferegov](https://api-publica.transferegov.gestao.gov.br/). Esses dados permitem investigar instrumentos e execução; a ligação ao parlamentar deve vir de autoria de emenda ou papel oficial comprovado. Parcerias estaduais/municipais e colaborações sem instrumento exigem fontes próprias, não uma inferência genérica por nome.

## Serviço geral proposto

Criar futuramente `src/service/public_career_coverage/`, separado de aquisição, identidade e projeção. Seu trabalho será comparar **escopo esperado**, **escopo efetivamente consultado** e **fatos ingeridos** por `person_id`, instituição, domínio e intervalo. Todos os candidatos entram na avaliação; domínios legislativos só se tornam aplicáveis quando houver exercício/mandato pertinente ou evidência de atuação. Pessoa sem cargo legislativo conhecido não deve receber centenas de buscas de projetos sem motivo.

Estados de cobertura devem distinguir `not_assessed`, `partial`, `complete_for_period`, `outdated`, `unavailable`, `identity_unverified` e `not_applicable`. `complete_for_period` requer prova de término da paginação/partição e cobertura da fonte; nunca apenas quantidade positiva. Período futuro não é lacuna. Fonte que não publica voto nominal não gera pedido infinito de voto individual.

Reutilizar `person_data_coverage` como resumo por pessoa/domínio/fonte, ampliando seu contrato mediante migração. A chave atual `(person_id, area, source_id)` representa apenas um resumo por combinação: não é suficiente para intervalos descontínuos ou várias instituições de uma mesma fonte. Preservar intervalos realmente consultados em metadados de artefatos existentes quando adequados; se necessário, criar um registro compacto de partições/intervalos, nunca duplicar todos os fatos da linha do tempo. Empresas e parcerias também exigem extensão explícita dos domínios permitidos, hoje limitados por CHECK.

**Não criar outra fila de pendências.** Reutilizar `person_data_gap`, ampliando de forma compatível o escopo da tarefa para domínio + instituição + intervalo, pois `UNIQUE(person_id, field_name)` atualmente não diferencia períodos/instituições. Uma alternativa mínima é uma pendência agregada por pessoa/domínio, cujo planejamento recalcula os intervalos faltantes a partir do registro de cobertura. Não guardar grandes listas de eventos na pendência. O orquestrador existente mantém agrupamento, lease, bloqueios e expurgo de processadas.

O fluxo será: avaliar em lotes → persistir somente lacunas → planejar recursos compartilhados → delegar ao crawler correto → normalizar/validar/identificar → ingerir fatos idempotentes → registrar cobertura efetiva → reavaliar → marcar processadas e expurgar conforme política atual. Erro parcial mantém os intervalos não consultados pendentes. A fila não serve como histórico dos fatos.

## Custo e controle de requisições

- Ler primeiro arquivos imutáveis e tabelas existentes. Planejar por fonte/instituição/ano/partição para servir várias pessoas com um download.
- Identificar recursos pelo URL/parâmetros normalizados e versão/hash; aproveitar downloader, cache, `source_request_policy`, advisory locks, leases e cooldown já implementados.
- Manter checkpoint de paginação e só declarar conclusão após todas as páginas. Retomar falhas sem recolher partições históricas já verificadas.
- Priorizar lacunas recentes e instituições com mandatos conhecidos; carregar histórico em lotes limitados. Revalidar proposições em tramitação com maior frequência que documentos encerrados, sem assumir que encerramento impede retificação futura.
- Respeitar `Retry-After` e bloqueios por host. Requisições de pessoas diferentes não devem baixar repetidamente a mesma votação ou norma.
- Avaliação completa tem custo proporcional aos dados/intervalos examinados, O(n), e não O(1). Hashes e índices ajudam deduplicação e consultas; não eliminam o custo de ler os registros necessários. Evitar N+1 de rede ou banco e O(n²) de cruzamento nominal.

## Prioridades e critérios de aceite

**Primeiro:** corrigir a semântica de cobertura de `political_activity` e implementar detalhes/tramitações/resultados da Câmara para as proposições já vinculadas. Em seguida, votos nominais, vínculo com leis e crawler municipal SP. Depois expandir instituições conforme carreira, e modelar empresas/parcerias com evidências adequadas.

Validar ao menos: pessoa com várias instituições/períodos; paginação interrompida; nenhuma proposição após consulta completa; tipos não PL; proposição acessória aprovada; votação simbólica; lei sem relação oficial suficiente; homônimos no QSA; coleta antiga ainda dentro de período incompleto. Verificar idempotência e reaproveitamento do mesmo recurso entre pessoas.

A interface pública deve exibir domínio, período e data de atualização, além de “histórico parcial” quando necessário. Não apresentar zero aprovações, zero empresas ou zero parcerias como conclusão pessoal enquanto a fonte correspondente não tiver sido efetivamente consultada e identificada.
