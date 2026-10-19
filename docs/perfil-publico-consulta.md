# Consulta pública de pessoas

O serviço `service.public_profile.people` compõe busca e cabeçalho somente a partir de tabelas canônicas privadas. O adaptador `database.public_people.PublicPeopleRepository` recebe uma conexão com permissão de leitura. Nenhuma requisição dispara coleta ou enriquecimento, abre originais, grava pendências ou devolve documentos pessoais.

## Contratos

`PeopleQuery(q='', uf=None, office_kind=None, political_party=None, cursor=None, limit=30)` valida filtros. `search_people(repository, query, as_of)` devolve `items`, `next_cursor` e `as_of`. Cada item contém `person_id`, `display_name` e `slug`. A busca considera exclusivamente o nome público; `%`, `_` e barra inversa são texto literal. A ordem é nome público e UUID interno, com paginação por chave. O cursor fica vinculado aos filtros e à data de referência; uma consulta no dia seguinte reinicia a paginação.

UF e cargo filtram exercícios documentados ativos na data da consulta; não reutilizam candidatura como prova de cargo atual. O filtro de partido considera a observação administrativa/filiação mais recente conhecida, sem usar declaração eleitoral como filiação atual. Esses filtros não certificam que a cobertura de todas as pessoas esteja completa.

`get_public_person(repository, person_id, as_of)` retorna nome público, UUID, slug, educação e os campos:

- `photo`: URL HTTPS em domínio institucional `.leg.br`, `.gov.br` ou `.jus.br`, com `status`; destinos com credenciais ou porta não padrão são rejeitados. A URL canônica precisa ter sido identificada corretamente na ingestão; o adaptador não reconhece rostos.
- `age`: idade e estado, sem divulgar nascimento. Pessoa nascida em 29/02 completa idade de apresentação em 01/03 no ano sem 29/02; isso não define uma regra jurídica.
- `political_party`: nome/sigla, `evidence_kind`, `observed_on` e `status`. Declaração eleitoral aparece como `electoral_declaration`; observação administrativa aparece como `observed`. Nenhuma delas ganha data fictícia de filiação. Divergência de partidos na mesma data resulta em `conflicting`.
- `current_offices`: todos os exercícios documentados ativos, com instituição e início individual. Não agrega tempo entre mandatos, não soma afastamentos e não duplica duração de exercícios sobrepostos do mesmo cargo/órgão: nesses casos a duração fica desconhecida com `overlapping_exercises`.
- `public_office`: indicador documentado e data da observação. Observação antiga permanece explicitamente histórica. Ausência de exercício não prova ausência de cargo.
- `payments`: última competência de cada combinação órgão/cargo/tipo de folha, com bruto, deduções e líquido como strings decimais. Não soma vínculos. `current_competence` identifica o mês corrente publicado; `latest_published` identifica até dois meses anteriores; `outdated` identifica competência mais antiga. Esse limiar é apresentação, não SLA oficial da fonte.
- `coverage`: `partial`, com indicador de truncamento. Um perfil não comprova cobertura integral da vida pública.

Ausência de fato gera valor nulo/estado desconhecido, nunca zero fictício. UUID inválido resulta em `INVALID_PERSON_ID`; pessoa inexistente ou alias privado resulta em `PERSON_NOT_FOUND`. O adaptador exclui aliases da busca e do perfil.

## Operação e custo

Busca: uma consulta parametrizada com até 101 resultados. Perfil: quatro consultas parametrizadas em uma transação consistente somente de leitura com timeout de cinco segundos. A composição custa O(k) em tempo e memória, com k limitado a 100 por categoria; não há N+1. A busca textual por trecho do nome público pode varrer a tabela, e os filtros por relações dependem dos índices existentes. Medir plano/latência antes de adicionar um índice de trigramas ou outra projeção de busca. O serviço não usa a visão materializada para evitar chamar retrato antigo de situação atual.

Os testes SQL criam um schema temporário com rollback obrigatório; dados demonstrativos nunca são inseridos no schema de produção. A aplicação web integra esses serviços separadamente.
