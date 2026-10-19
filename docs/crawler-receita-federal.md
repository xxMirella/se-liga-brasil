# Receita Federal: empresas, estabelecimentos e participações

Implementação em `src/crawlers/receita_federal/`, verificada em 17/10/2026 com arquivos fictícios locais. Não houve download da base nacional, alteração de originais, aplicação de migração nem ingestão em produção.

## Fonte e limites verificados

O [layout oficial do CNPJ](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf/@@download/file) separa empresas (7 campos), estabelecimentos (30 campos) e sócios (11 campos). O CSV usa ponto e vírgula. O parser lê os arquivos CP1252 diretamente dentro do ZIP; não extrai nem reescreve originais. Mudança no número de campos interrompe o processamento, sem declarar a partição concluída.

O QSA publica qualificação e data de entrada. Os CPFs são descaracterizados: ocultação dos três primeiros e dois últimos dígitos. Faixa etária não é data de nascimento. A data de situação cadastral pertence ao estabelecimento, não à saída de um sócio. Capital social pertence à empresa e não comprova patrimônio individual nem renda recebida.

A navegação do catálogo nos hosts oficiais `arquivos.receitafederal.gov.br` e `dadosabertos.rfb.gov.br` não ficou disponível na verificação desta implementação (404/indisponibilidade). Portanto o módulo **não anuncia um snapshot atual descoberto**, não inventa URLs válidas e não usa espelhos comerciais. Recebe URLs oficiais selecionadas e mês explícito, validando host, HTTPS, mês no caminho e nomes `EmpresasN.zip`, `EstabelecimentosN.zip` ou `SociosN.zip`. Essa validação estrutural não garante que o recurso exista: a aquisição precisa confirmar a resposta HTTP.

## APIs e reaproveitamento

- `CrawlerConfiguration(storage_directory=...)`: limites explícitos por recurso, execução, descompressão, membros, registros e fatos selecionados. Padrões conservadores: 100 MiB por download, 200 MiB na execução, 3 recursos, 500 MiB descomprimidos e 10 mil fatos por categoria. Partições nacionais podem exceder esses limites; o erro é deliberado, sem aumento automático.
- `plan_resources(snapshot_month, selected_urls, configuration)`: planejamento sem rede, deduplicado. Deve ser executado antes de baixar. As partições não são distribuídas por nome de pessoa: não é possível descobrir uma pessoa baixando apenas uma partição arbitrária e concluir ausência nacional.
- `acquire_resources(resources, configuration, client)`: reutiliza `service.acquisition.downloader.download_resource`, `DownloadBudget`, manifests, cache por hash, validação HTTP e limites. O `client` é `OfficialHttpClient(configuration, httpx_client, OFFICIAL_HOSTS)`; preserva pacing, retry e cooldown existentes.
- `scan_snapshot(artifacts, people, configuration, observed_on=..., reviewed_relationships=...)`: processa o conjunto de pessoas em lote. `people` contém somente `person_id` interno e `full_name`. Cada partição CSV selecionada é percorrida uma vez. Primeiro lê QSA; depois lê empresas e estabelecimentos para as bases empresariais encontradas. Retorna `SnapshotFacts` com categorias separadas e hashes das partições integralmente percorridas.
- `ReviewedRelationship(person_id, evidence_url, reviewed_by, reviewed_at)`: revisão explícita da identidade e do vínculo, indexada por `artifact.sha256 + ':' + partner_evidence_key(row)`. O vínculo deve ser sustentado por evidência pessoal/registral independente revisada; a coincidência de nome e CPF mascarado não basta. A revisão valida pessoa pertencente aos candidatos nominais, URL HTTPS e timestamp com fuso, mas a veracidade da evidência ainda depende do processo de revisão.
- `stage_snapshot_facts(artifact, facts, configuration)`: produz derivado privado `ValidatedArtifact`, verificando hash do original. Só vínculos revisados são exportados à ingestão. Candidatos ambíguos permanecem no retorno local da análise; CPF do sócio não é exportado. O escopo inclui hash dos fatos selecionados/revisados: mudar seleção ou revisão não será indevidamente ignorado como artefato já concluído.
- `BusinessProjectionWriter(writer)`: executa SQL em lotes por meio do `SqlBatchWriter` existente.
- `ingest_snapshot_facts(artifacts, facts, configuration, repository)`: recebe `IngestionRepository` com execução já iniciada, fonte `receita_federal`, projetor acima e `parser_version='receita-cnpj-v1'`. Não cria conexão, não inicia execução, não aplica schema e não coleta implicitamente. Ignora artefatos sem fatos canônicos elegíveis.

O coletor usa normalizadores existentes de nome, texto, dinheiro e datas; storage, hash, staging, arquivo validado e ingestão transacional seguem os contratos do projeto. Hashes de observação identificam evidência técnica, nunca substituem `person_id`.

## Tabelas propostas e SQL

A migração **não aplicada** `db/migrations/0016_business_relationships.sql` cria:

- `business`: identidade empresarial pelo CNPJ básico, razão social, natureza, capital social, porte, mês do snapshot, data de observação e fonte. Uma linha pode começar apenas com a base empresarial quando não foi baixada a partição de empresas; nome ausente não é inventado.
- `business_establishment`: CNPJ completo, matriz/filial, situação cadastral, datas publicadas, CNAE principal, UF/município, snapshot e fonte.
- `person_business_relationship_observation`: `person_id`, empresa, qualificação oficial, entrada, saída comprovada opcional, snapshot, observação, evidência e revisão, fonte. Apenas revisão explícita permite esse vínculo.

As tabelas ficam privadas, com RLS habilitado e sem grants públicos. SQL de projeção: `db/ingestion/receita_federal_business.sql`. Reutiliza `source_record`, `ingestion_entity`, versões e artefatos existentes para rastreabilidade e replay. A pessoa segue identificada exclusivamente pelo UUID interno. Empresas usam sua própria chave cadastral; não são identificadores pessoais de provedores.

A projeção preserva observações societárias e nunca encerra um vínculo pela ausência em snapshot posterior. `exited_on` permanece nulo neste coletor porque o layout examinado não fornece saída. `snapshot_month`, `observed_on` e `entered_on` são conceitos diferentes. A observação factual deriva da aquisição original (`artifact.fetched_at`); `observed_on` passado à análise é a data limite da análise. Reanalisar o mesmo arquivo em outro dia não altera sua observação nem produz conflito de timestamp. Uma revisão humana nova tem sua própria versão identificada por pessoa, evidência, revisor e data da revisão; preserva auditoria sem fabricar um novo ingresso societário. Empresas e estabelecimentos mantêm projeção atual ordenada por mês de snapshot e observação, impedindo que um snapshot antigo baixado hoje substitua um mais recente. Versões originais ficam nos registros de ingestão. Registros classificados como conflitantes ou antigos pela reconciliação não alteram projeções.

## Complexidade, custo e cobertura

Se P é o número de pessoas e N o total de linhas nos arquivos selecionados, o custo principal é O(P + N), acrescido dos candidatos nominais efetivamente retornados. Busca nominal e deduplicação usam hashes, com custo médio O(1) por consulta. Homônimos geram conjunto de candidatos, sem cruzamento completo de pessoas por linha. A memória é O(P + M + C), em que M representa os fatos selecionados limitados por configuração e C as referências de candidatos retornadas; grupos de homônimos podem aumentar C. Hash de arquivo para cache/integridade exige leitura adicional de bytes; não é uma nova varredura de CSV por pessoa. Consultas PostgreSQL indexadas não são prometidas como O(1).

Plano pequeno serve para validação operacional e análise seletiva. Cobertura nacional de QSA exige todas as partições aplicáveis, com orçamento planejado; filtrar resultados localmente não reduz os bytes necessários do ZIP remoto. Os hashes retornados provam apenas as partições selecionadas integralmente percorridas, não ausência nacional de empresas, histórico completo nem início/fim da vida empresarial.

## Integração pendente

O módulo já é chamável para aquisição limitada, análise local, staging e ingestão pelo repositório existente. A migração e a projeção SQL foram exercitadas em schemas isolados com rollback; não foram aplicadas em produção. O registro da migração no instalador/fixture é tratado pela integração geral do projeto. Não foram adicionados comandos CLI, rotas de orquestração nem domínios de completude: o serviço de cobertura deverá planejar snapshots compartilhados, registrar partições realmente consultadas e encaminhar candidatos à revisão. Sem esse registro e catálogo acessível, não declarar empresas como domínio completo nem resolver pendências por resultado vazio.

## Validação executada

Quatorze testes locais cobrem limites de ZIP/CSV, mudança de layout, replay determinístico, deduplicação, lote de pessoas com uma leitura por partição, homônimos/CPF mascarado sem confirmação, revisão com data/evidência, exclusão de vínculos não revisados da ingestão e mudança de escopo após revisão. Dois testes SQL adicionais validam migração, empresas, estabelecimentos, exclusão de vínculo não revisado, inclusão de vínculo revisado, replay sem duplicação, reanálise em outro dia e preservação de versões da revisão. Esses testes usam schema isolado e rollback obrigatório; nenhum dado fictício permanece no banco. Ruff e revisão estrutural do projeto passaram. Não houve escrita em tabelas de produção.
