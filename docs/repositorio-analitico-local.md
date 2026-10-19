# Datasets locais de votos

PostgreSQL continua como base canônica. Parquet com DuckDB oferece consultas analíticas locais sem serviço pago obrigatório. Instale o extra Python `analytical` para os comandos analíticos; os crawlers não dependem de DuckDB.

`build-dataset --source senado --years YYYY` exporta votos canônicos com identidade validada, usando leitura consistente e lotes limitados, e publica Parquet comprimido. `--dataset-directory` seleciona o repositório. `--input-file` aceita NDJSON no contrato estrito do módulo, não arquivos arbitrários das fontes.

`query-dataset --source senado --years YYYY --person-id UUID` consulta uma pessoa; `--start-date`, `--end-date` e `--limit` delimitam o resultado. As datas são inclusivas. O UUID é interno; `voting_id` é a chave numérica interna da votação. Documentos pessoais e nomes não fazem parte desse dataset.

O manifesto contém partição, versão, hashes e quantidade. A publicação valida os dados antes da troca atômica, deduplica votos e rejeita fatos conflitantes. A consulta verifica a integridade do Parquet. O padrão limita entrada a 64 MiB, linha a 16 KiB e repositório a 256 MiB. Versões derivadas antigas contam nesse limite; não há expurgo automático desses arquivos.

Uma partição vazia ou publicada não comprova ausência de atuação. `collection_complete` permanece falso sem certificação adicional. O primeiro contrato cobre votos individuais, não todo o universo de leis, empresas e parcerias. O backend público ainda precisa de um adaptador de consulta e de uma política explícita de atualização; a prévia visual continua demonstrativa.

## Contrato e reprocessamento

O módulo `service.analytical_datasets` expõe `publish_person_votes(input_path, repository_path, partition, parser_version)` e `query_person_votes(repository_path, partition, person_id, start_on, end_on, limit=100)`. `DatasetPartition` recebe instituição, ano e `collection_complete=False`. Uma partição é compartilhada por todas as pessoas dessa instituição/ano; não existe um arquivo por pessoa.

Cada linha NDJSON contém exclusivamente `person_id`, `voting_id`, `institution_code`, `occurred_on`, `date_precision`, `vote_choice`, `participation_status`, `evidence_sha256` e `validation_status`. O status precisa ser `verified`; campos adicionais são rejeitados, inclusive documentos e identificadores pessoais externos. Essa marca não substitui o trabalho de validação anterior: uma entrada manual que declare falsamente validação não recebe comprovação adicional pelo exportador.

O dataset conserva datas com precisão `day`, `month` ou `year`. Os limites `event_start_on`/`event_end_on` são intervalos auxiliares para pesquisa por sobreposição, e não datas de evento inventadas. Um registro com precisão mensal continua mostrando apenas mês/ano. Escolha favorável, contrária, abstenção e obstrução exigem participação `voted`; presidência, ausência e presença sem registro de voto permanecem separados e com escolha nula. O contrato ainda não representa nominal indisponível de uma votação inteira: isso pertence aos datasets futuros de votação e cobertura.

A publicação recebe **snapshot integral dos fatos conhecidos da partição**, mesmo quando a coleta oficial ainda é incompleta. Não enviar apenas as linhas novas: elas substituiriam a visão corrente das anteriores. A incrementalidade implementada é por partição/conteúdo/versão de parser, não um merge por linha. Releitura idêntica verifica o hash do Parquet e retorna o manifesto existente. Mudança efetiva ou nova versão de parser gera uma publicação, deduplicando fatos idênticos e rejeitando duas versões conflitantes de uma mesma chave pessoa/votação. Retificação pode substituir o voto no novo snapshot sem criar duas escolhas correntes.

Uma geração recebe nome pelo hash do Parquet; o arquivo é sincronizado antes da troca atômica do manifesto. O diretório também é sincronizado. Se o processamento falhar antes da troca, o manifesto anterior continua válido. O lock não bloqueante permite somente um escritor no repositório; escritor concorrente recebe erro para reagendamento. Leitores obtêm um manifesto inteiro e a geração imutável a que ele aponta. Gerações anteriores não são apagadas automaticamente: preservam leitores em andamento e rastreabilidade, mas exigirão política explícita de retenção.

## Custos e limites reais

A normalização percorre n registros em O(n), com uma linha de até 16 KiB em memória Python e leitura de hash em blocos de 1 MiB. Deduplicação/ordenação no DuckDB podem consumir O(n) de armazenamento intermediário e O(n log n) na ordenação; o processamento completo não é O(1). Consultas recebem no máximo mil resultados, porém a checagem integral do hash custa O(bytes da partição) antes da leitura filtrada. Portanto esse comando é uma ferramenta analítica em lote, não o caminho de uma requisição pública por pessoa.

O DuckDB recebe limite de 256 MiB para seu gerenciador de memória, duas threads e até 512 MiB de spill temporário. Esse limite de memória não é uma garantia de RSS total do processo. A entrada aceita até 64 MiB e o repositório tem orçamento conservador padrão de 256 MiB: a verificação conta arquivos persistidos e temporários existentes, podendo rejeitar antes do limite final de arquivos permanentes. O orçamento é verificado antes da publicação e não reserva espaço de disco contra processos externos. Durante processamento, entrada normalizada e spill podem exceder o orçamento de publicação; reservar espaço adicional e monitorar disco continua necessário. Nenhuma infraestrutura paga ou hospedagem externa é exigida.

As gerações antigas contam no orçamento. Corrigir/reexecutar indefinidamente não ocupa disco sem limite: a publicação passa a falhar explicitamente quando o orçamento termina. Aumentar esse valor ou remover gerações deve ser uma decisão operacional, preservando backup e leitores; não existe expurgo implícito de originais. Fontes originais não são modificadas pelo serviço, e o hash de evidência liga o fato à proveniência já validada.

## Validação e entregas ainda abertas

A suíte local usa DuckDB/Parquet reais em diretórios temporários, sem banco de produção: replay, deduplicação, correção, nova versão de parser, integridade, troca interrompida, orçamento, datas parciais, partição vazia e rejeição de campos indevidos. O esquema do manifesto também é validado antes de abrir seus caminhos, evitando traversal e versões incompatíveis.

Este entregável demonstra exportação e pesquisa de **votos individuais**. Permanecem separados: datasets de votações/eventos legislativos/leis/autorias/cobertura, certificação da completude por intervalo, checkpoints de aquisição oficial, política de retenção e sincronização transacional de novas projeções para a API. O manifesto concluído é um checkpoint de construção do derivado, não uma certificação de paginação completa da fonte. A aplicação deve continuar lendo tabelas PostgreSQL; não há adaptador neste serviço que carregue Parquet durante a visita ao perfil.

Referências: [API Python oficial do DuckDB](https://duckdb.org/docs/current/clients/python/overview) e [documentação oficial de Parquet](https://duckdb.org/docs/stable/data/parquet/overview). O ambiente de desenvolvimento foi validado com DuckDB 1.5.6; a dependência opcional permite `>=1.4,<2`.

## Projeção pública simples de votação

`publish_person_voting_timeline(input_path, repository_path, partition, parser_version)` acrescenta o contrato **`person_voting_timeline.v1`**. O dataset anterior `person_votes.v1` permanece disponível e inalterado em seu diretório. O novo dataset ocupa `legislative/{institution}/person_voting_timeline/year=AAAA/`, com uma linha por **pessoa e votação**, preservando votações distintas de turnos, emendas e destaques. Não é uma linha por lei nem presume que a proposição tenha se tornado lei.

A entrada validada recebe os campos de `person_votes.v1` e mais `matter_kind`, `matter_number`, `matter_year`, `matter_name`, `description`, `description_origin`, `official_url`, `voting_subject` e `round_number`. Campos desconhecidos são nulos; a origem da descrição deve ser `official_text`, `curated_summary` ou `unknown`. Evidência e status de validação são exigidos exclusivamente para validar a entrada: **`evidence_sha256` e `validation_status` não são publicados nas colunas do Parquet público**.

A saída contém pessoa interna, votação interna, instituição, data/precisão e limites auxiliares de pesquisa, escolha individual e participação, identificação/nome da matéria, objeto votado e turno. Também contém `short_description`, `description_kind`, `description_state`, URL oficial e estados de disponibilidade dos textos/identificadores desconhecidos. Texto oficial com mais de 280 caracteres é apenas recortado e marcado `official_excerpt`; não se produz resumo interpretativo. Curadoria declarada permanece distinguida como `curated_summary` ou `curated_excerpt`. Descrição ausente exige origem `unknown`, e não recebe texto inventado. Esses rótulos registram a origem informada pelo exportador; revisão editorial e validação de fonte continuam sendo responsabilidades anteriores ao publisher.

Links são HTTPS em domínios governamentais/legislativos brasileiros, sem credenciais, porta ou fragmento; o publisher não fabrica endereço da proposição. Texto ou link inexistente produz valor nulo com estado `missing`. Cada entrada mantém o objeto da votação e turno, evitando apresentar voto de destaque como escolha sobre toda a matéria. Ausência, presidência e informação indisponível não viram voto contrário.

O publisher reutiliza o mesmo fluxo de validação em streaming, limites, lock, geração Parquet, detecção de conflitos e troca atômica de manifesto do dataset anterior. Publicação remota não foi implementada nem realizada. A aplicação pública continua consultando tabelas canônicas, sem abrir Parquet por visita. Testes reais verificam coexistência dos contratos, replay, múltiplos turnos, ausência de campos privados, recorte explícito, campos desconhecidos, links indevidos, rejeição de fatos não verificados e conflitos.
