# Crawler Senado

Implementado em `src/crawlers/senado/`, com entrada `collect_senado_enrichment(connection, storage, people, fields=None)`.

## Cobertura executável

`SUPPORTED_FIELDS`: `current_public_office`, `current_political_party`. Uma lista corrente é baixada por lote, indexada pelo nome completo; somente candidatos únicos seguem para o perfil individual, que confirma nome completo + nascimento por `match_official_person`. Nome isolado só seleciona um candidato remoto, nunca vincula pessoa. Não cria pessoas nem persiste códigos externos como identidade pessoal.

A lista oficial identifica explicitamente senadores em exercício, mandato e períodos de exercício. O perfil fornece nascimento, nome completo e partido. São projetados mandato, exercício, observação partidária e `person_fact.current_public_office_observation`, depois o snapshot geral da pessoa. Ausência na lista nunca produz flag falsa. Histórico de filiação jurídica completo não é inferido da observação partidária atual.

Artefatos originais imutáveis ficam sob cache compartilhado; um bundle com hashes de lista e perfil invalida a ingestão quando qualquer dependência muda. Limites: 25 pessoas por execução, 20 MiB por arquivo, 100 MiB por execução, cache 24h, pacer e circuit breaker compartilhados. Cada pessoa exige um perfil remoto único quando o cache expira; não existe promessa O(1) para rede. Índice custa O(s) tempo/memória; varredura dos pedidos O(p+a), sendo a os aliases pessoais.

## Limites comprovados em 17/10/2026

Amostras oficiais de lista e perfil preservadas em `data/private/senado-atual.json` e `data/private/senado-profile.json`. API de autorias retornou HTTP503 durante validação; a implementação não afirma cobertura de atividade legislativa. O portal remuneração liga senadores ativos às páginas individuais; nenhum layout nominal de folha foi validado para ingestão nesta frente. `current_salary` e `political_activity` são retornados em `unsupported_fields`; pedidos exclusivamente desses campos não fazem requisições nem acessam banco. O orquestrador deve bloquear essas capacidades até implementação validada, e não marcar pendência como atendida.

Não houve ingestão em massa de produção nesta frente. A autoria futura deverá distinguir coautoria, relatoria e aprovação. Subsídio tabelado e CEAPS não comprovam pagamento salarial individual.

Fontes oficiais:
- https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json
- https://legis.senado.leg.br/dadosabertos/senador/{codigo}.json
- https://www12.senado.leg.br/transparencia/sen/senadores
- https://www12.senado.leg.br/transparencia/rh/segp/remuneracao-e-subsidio-recebidos

## Validação

Três testes unitários passaram (normalização de exercício explícito, seleção de candidato remoto, pedidos não suportados sem I/O). Um teste de integração PostgreSQL passou em schema isolado com rollback: mandato/exercício/filiação são projetados, `person.has_current_public_office=true`, `current_public_office_kind=senator` e segunda ingestão é ignorada sem duplicar fatos. Ruff e revisão estrutural sem achados.

Fim explícito de exercício é preservado como intervalo exclusivo (`DataFim + 1 dia`), inclusive quando futuro. A projeção atualiza o período somente por evidência mais recente; ausência posterior de data de fim não reabre exercício encerrado. A observação corrente inclui `exerciseEndExclusive` para respeitar esse limite. Parser `senado-personal-python-v2`.
