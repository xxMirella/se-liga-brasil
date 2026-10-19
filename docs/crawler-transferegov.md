# Coletor de instrumentos e recursos federais

## Estado e contratos validados

Em 17/10/2026, os contratos oficiais `parcerias/openapi.json` e `especiais/openapi.json` responderam HTTP 200. Duas consultas mínimas a `/parcerias/parceria` e `/parcerias/proposta`, com `pagina=1&tamanho_da_pagina=1`, responderam HTTP 200, com um registro cada. O envelope observado contém `data`, `total_pages`, `total_items`, `page_number` e `page_size`; a documentação limita a página a 200 registros. A amostra informou 89.612 registros em cada endpoint. Esse total é uma observação daquele instante, não uma garantia de cobertura histórica.

Fontes: [portal oficial de APIs](https://api-publica.transferegov.gestao.gov.br/), [contrato Gestão de Parcerias](https://api-publica.transferegov.gestao.gov.br/parcerias/openapi.json), [contrato Transferências Especiais](https://api-publica.transferegov.gestao.gov.br/especiais/openapi.json) e [publicação institucional sobre dados abertos](https://www.gov.br/transferegov/pt-br/ferramentas-gestao/dados-abertos).

O conector também executou duas consultas filtradas por chave de fato, uma por domínio, normalizando um registro em cada. Os originais foram preservados em `data/transferegov/archives` e os manifestos em `data/transferegov/manifests` (1.436 e 9.667 bytes). Não foram feitas consultas por nome nem varredura completa.

A aquisição e normalização estão implementadas e testadas. **Não houve ingestão no banco, aplicação de migração ou integração deste conector ao CLI/orquestrador.** A operação remota foi verificada nas duas amostras acima; os demais domínios foram conferidos no OpenAPI e em testes locais, sem uma coleta histórica completa. Nenhuma pendência pode ser marcada resolvida somente por existir este módulo.

## Responsabilidades dos módulos

`src/crawlers/transferegov/configuration.py` define fonte, filtros permitidos e orçamento. `acquisition.py` valida partições e paginação. `normalization.py` separa instrumentos, propostas, organizações e ordens financeiras. `identity.py` aceita vínculos pessoais revisados. `pipeline.py` percorre partições únicas e emite fatos normalizados com URL oficial, SHA-256 e instante de observação.

A aquisição reutiliza `service.acquisition.downloader.download_resource` e `OfficialHttpClient`: arquivos por hash, manifesto HTTP, cache de 24 horas, limites por arquivo/execução, retry limitado para falhas transitórias, pausa entre requisições e cooldown compartilhado em 403/429. Arquivos baixados não são reescritos para normalizar dados. O construtor recebe um cliente de transporte e configuração, permitindo testes isolados e outras estratégias de execução.

Assinaturas públicas:

```python
TransferegovAcquisition(configuration, official_http_client)
acquisition.pages(module, endpoint, filters)
collect_records(acquisition, module, endpoint, partitions)
index_reviewed_participations(participations)
attach_reviewed_participation(record, indexed_participations)
```

`pages` emite `(rows, artifact)`. `collect_records` emite dicionários normalizados e nunca executa SQL. Um consumidor futuro deve gravar em lotes/arquivo derivado temporário e só confirmar a cobertura da partição após o gerador terminar sem erro. Limites excedidos e páginas repetidas geram erro explícito, sem declarar coleta completa.

## O que cada domínio informa

- `parcerias/parceria`: identificador do instrumento, proposta relacionada, situação, assinatura e autorização de execução. Assinatura e autorização não viram datas de vigência.
- `parcerias/proposta`: objeto, situação, valor planejado e organizações com os papéis distintos de recebedor, executor e terceiro signatário. Endereços e campos pessoais desnecessários não integram a saída normalizada.
- `parcerias/ordem-pagamento`: documento financeiro relacionado, emissão, situação, valor ordenado e emissão de ordem bancária. `ordered_amount` é diferente de `executed_amount`, que permanece desconhecido nesta etapa.
- `parcerias/indicacao-beneficiario-emenda-parlamentar`: indicação e beneficiário, com tipo de apoiador. Nome ou identificador mascarado não cria vínculo automático com pessoa.
- `especiais/planos-acao-especiais`: objeto, situação, aceite, número da emenda e valores separados de custeio e investimento. Código pessoal do parlamentar não é persistido na saída normalizada.

Todos os valores monetários são strings decimais normalizadas, com leitura JSON via `Decimal`, evitando passagem por ponto flutuante. Datas ausentes ficam nulas. O crawler mantém observações de situação, não fabrica um histórico SCD2 a partir de um snapshot.

## Partições e custo

Filtros são obrigatórios e precisam pertencer ao contrato permitido do endpoint. Exemplos genéricos: proposta por `ano_proposta` e `sg_uf_recebedor`; instrumento por `id_proposta`; transferência especial por `ano_plano_acao`. IDs de instrumento/proposta são chaves de fatos, não identificadores pessoais. Filtros de nome parlamentar não são aceitos para resolver identidade.

Uma execução recebe o conjunto de partições necessário a várias pessoas. Partições iguais são consultadas uma vez; registros sobrepostos são deduplicados por chave do fato. Uma mudança de conteúdo para a mesma chave durante a coleta gera `TRANSFEREGOV_SNAPSHOT_CONFLICT`, exigindo reavaliação em vez de escolher silenciosamente uma versão.

O custo total é O(n + p), para n registros lidos e p partições recebidas, com busca/deduplicação média O(1) por chave. A memória de deduplicação é O(u + q), limitada pelas configurações de registros e partições únicos. Isso não promete leitura O(1) da base inteira. Há ainda uma requisição por página não atendida pelo cache, não uma por pessoa. Os limites padrão são 20 páginas por partição, 100 registros por página, 2.000 fatos únicos, 20 partições, 20 MiB por arquivo e 80 MiB por execução.

## Identidade e significado dos vínculos

`ReviewedParticipation` exige `person_id` interno, chave do fato, hash do arquivo e referência de revisão. Os papéis admitidos são `amendment_author` e `formal_signatory`. O vínculo só vale para o arquivo revisado. Troca de hash mantém a pessoa desconhecida até revisão; nomes isolados, foto e coautoria não são provas.

Uma organização executora não torna seu dirigente ou o autor da emenda executor pessoal. Indicação orçamentária não prova entrega, parceria informal, aprovação parlamentar ou resultado de política pública. O método não atribui automaticamente uma participação pessoal ao conjunto de instrumentos de um município.

## Integrações que ainda faltam

A persistência precisa separar instrumento/proposta, participação institucional, participação pessoal revisada, emenda e fatos financeiros. Reutilizar `source_record` para proveniência; não duplicar corpos completos dos documentos no banco. O orquestrador deve agrupar tarefas por fonte, domínio, ano/UF e instrumento, evitando consultas por candidato.

Para comprovar execução, faltam normalizadores e joins dos endpoints de empenhos, documentos hábeis, extratos e execução financeira, com regras para cancelamentos, devoluções e estágios. Não se deve somar indistintamente valor planejado, empenhado, ordenado, pago e executado. A API tem recursos adicionais, mas eles ainda não estão implementados neste conector.

Vigência contratual exige campo ou documento oficial próprio. Prazo de captação não é vigência. Transferências Discricionárias e Legais também têm exportação CSV oficial; este trabalho não fez download completo nem implementou seu parser. Portais estaduais/municipais e parcerias sem instrumento federal exigem outros contratos e não estão cobertos por Transferegov.

## Validação

Testes isolados cobrem deduplicação entre partições, preservação/cache de originais, retry 503, cursor/página repetida, limite de páginas/bytes/registros/partições, precisão decimal, conflito entre snapshots e revisão de identidade vinculada ao hash. Não há registros fictícios gravados em produção.
