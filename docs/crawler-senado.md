# Crawler Senado

Implementado em `src/crawlers/senado/`, com entrada `collect_senado_enrichment(connection, storage, people, fields=None)`.

## Cobertura executável

`SUPPORTED_FIELDS`: `current_public_office`, `current_political_party`, `photo_url`, `current_office_started_on` e `current_salary`. Uma lista corrente é baixada por lote, indexada pelo nome completo; somente candidatos únicos seguem para o perfil individual, que confirma nome completo + nascimento por `match_official_person`. Nome isolado só seleciona um candidato remoto, nunca vincula pessoa. Não cria pessoas nem persiste códigos externos como identidade pessoal.

A lista oficial identifica explicitamente senadores em exercício, mandato e períodos de exercício. O perfil fornece nascimento, nome completo e partido. São projetados mandato, exercício, observação partidária e `person_fact.current_public_office_observation`, depois o snapshot geral da pessoa. Ausência na lista nunca produz flag falsa. Histórico de filiação jurídica completo não é inferido da observação partidária atual.

Artefatos originais imutáveis ficam sob cache compartilhado; um bundle com hashes de lista e perfil invalida a ingestão quando qualquer dependência muda. Limites: 25 pessoas por execução, 20 MiB por arquivo, 100 MiB por execução, cache 24h, pacer e circuit breaker compartilhados. Cada pessoa exige um perfil remoto único quando o cache expira; não existe promessa O(1) para rede. Índice custa O(s) tempo/memória; varredura dos pedidos O(p+a), sendo a os aliases pessoais.

## Diagnóstico histórico de 17/10/2026

Amostras oficiais de lista e perfil preservadas em `data/private/senado-atual.json` e `data/private/senado-profile.json`. API de autorias retornou HTTP503 durante validação; a implementação não afirma cobertura de atividade legislativa. O portal remuneração liga senadores ativos às páginas individuais; nenhum layout nominal de folha foi validado para ingestão nesta frente. Naquele momento, `current_salary` e `political_activity` eram não suportados. A integração nominal de remuneração descrita abaixo substitui essa limitação para `current_salary`; atividade legislativa continua exigindo implementação própria.

Não houve ingestão em massa de produção nesta frente. A autoria futura deverá distinguir coautoria, relatoria e aprovação. Subsídio tabelado e CEAPS não comprovam pagamento salarial individual.

Fontes oficiais:
- https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json
- https://legis.senado.leg.br/dadosabertos/senador/{codigo}.json
- https://www12.senado.leg.br/transparencia/sen/senadores
- https://www12.senado.leg.br/transparencia/rh/segp/remuneracao-e-subsidio-recebidos

## Validação

Três testes unitários passaram (normalização de exercício explícito, seleção de candidato remoto, pedidos não suportados sem I/O). Um teste de integração PostgreSQL passou em schema isolado com rollback: mandato/exercício/filiação são projetados, `person.has_current_public_office=true`, `current_public_office_kind=senator` e segunda ingestão é ignorada sem duplicar fatos. Ruff e revisão estrutural sem achados.

Fim explícito de exercício é preservado como intervalo exclusivo (`DataFim + 1 dia`), inclusive quando futuro. A projeção atualiza o período somente por evidência mais recente; ausência posterior de data de fim não reabre exercício encerrado. A observação corrente inclui `exerciseEndExclusive` para respeitar esse limite. Parser atual `senado-personal-python-v4`.

## Diagnóstico da remuneração em 22/10/2026

O índice oficial de CSV mensal publica setembro/2026 em
`https://www.senado.leg.br/transparencia/LAI/secrh/SF_ConsultaRemuneracaoServidoresParlamentares_202609.csv`.
O arquivo consultado tem vínculo, categoria, cargo, lotação, tipo de folha e
componentes financeiros, mas não tem nome nem identificador pessoal do beneficiário.
Não é possível ligar linhas a pessoas a partir de lotação ou valor do subsídio.
A lotação de um gabinete também inclui pagamentos de servidores.

A página individual de transparência publica o link `detalhe.asp?fcodigo=…&fvinculo=2`
para o subsídio do senador. A resposta examinada apresenta seleção de competência,
CAPTCHA e nenhum demonstrativo nominal na requisição inicial. Esse diagnóstico inicial foi superado pela validação da API nominal administrativa,
documentada em [fonte-api-remuneracao-senado.md](fonte-api-remuneracao-senado.md).
O crawler agora suporta `current_salary` a partir dessa API pública. O CSV anônimo e a
tabela legal de subsídios não servem para completar esse campo.

Fontes verificadas: [consulta mensal de remuneração](https://www.senado.leg.br/transparencia/rh/servidores/consulta_remuneracao.asp)
e [remuneração e subsídio recebidos](https://www12.senado.leg.br/transparencia/rh/segp/remuneracao-e-subsidio-recebidos).


## Remuneração nominal pela API administrativa

Fonte, contrato, limites de identidade e cálculo estão em
[API nominal de remunerações do Senado](fonte-api-remuneracao-senado.md).
A cadeia executável usa `payroll_acquisition.py`, `payroll.py`, `payroll_pipeline.py`,
`staging.py` e a projeção `db/ingestion/senado_payroll.sql`, sobre a ingestão genérica.
A folha normal e os complementos compõem um único pagamento mensal por pessoa;
os componentes originais e os tipos de folha permanecem preservados.

A mudança de capacidade reativa somente as pendências de salário bloqueadas pelo
antigo `SOURCE_FIELD_NOT_SUPPORTED`. Outros bloqueios de identidade e as políticas
de cooldown são preservados. Um sucesso técnico sem pagamento válido não resolve a
pendência. A consulta pública lê a projeção persistida; nunca chama o crawler.
