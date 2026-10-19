# Modelo de dados — Se Liga Brasil

## Situação

Nomenclatura explícita: `political_party`, `political_party_affiliation` e `political_party_id`. A migração de bancos com os nomes anteriores está em `db/migrations/0002_explicit_political_party_names.sql`, com renomeação transacional, sem recriar ou excluir dados.

Desenho e SQL inicial em `db/schema.sql`. **Aplicado em 6 de outubro de 2026 ao PostgreSQL 17.6**, inicialmente com 23 tabelas, RLS habilitada em todas e uma visão materializada. As migrações de ingestão, identidade e filiação elevaram o total a 36 tabelas privadas. A carga atual está limitada a SP e RJ; partidos, vínculos eleitorais e contexto histórico possuem registros próprios. Consulte `identidade-filiacao-e-contexto.md` para os critérios de associação e validade. O `.env` de `mdqc-knowledge-center` contém a conexão PostgreSQL em `SUPABASE_URL`. Credenciais não foram copiadas para este projeto; o processo administrativo carrega esse arquivo externamente. A chave de outro serviço existente no arquivo não é usada.

O schema proposto é `se_liga_brasil`. A aplicação inicial falha se ele já existir, evitando sobrescrever um schema sem inspeção. O SQL usa uma transação e timeouts; não altera tabelas, grants ou search_path da contabilidade, nem instala extensões globais. PostgreSQL 17+ é o alvo desta versão.

## Validação local

Executar `.venv/bin/pytest -q` para testes locais de normalização, arquivos, comparação genérica e revisão estrutural. Os testes SQL marcados como `integration` exigem uma conexão explícita; criam um schema isolado dentro de transação com rollback obrigatório. A suíte original de comportamento relacional foi mantida em `db/tests.sql` e é executada nesses testes. A extensão de ingestão adiciona nove tabelas privadas, descritas em [crawler e ingestão](crawler-e-ingestao.md). Não há benchmark de produção nesta versão.

## Decisão principal

Manter a base de escrita relacional e usar uma **visão materializada por pessoa** para a leitura dos cards. O perfil repete nome, partido observado, cargos em exercício e contagens. Essas cópias são derivadas e reconstruíveis, com `refreshed_at`; não são uma segunda fonte editável.

A duplicação fica restrita ao modelo de leitura. Os relacionamentos pessoa↔proposta, pessoa↔voto e pessoa↔emenda ficam em tabelas próprias com chaves e índices. Não armazenar toda a carreira num JSON gigantesco nem carregar todos os trabalhos para abrir um card.

## Entidades

| Grupo | Tabelas | Função |
| --- | --- | --- |
| Origem | `source`, `source_record` | Órgão, método, URL, chave externa, hash, coleta, validade e conteúdo ou referência ao arquivo |
| Pessoa | `person`, `person_identifier`, `person_fact` | Identidade canônica por UUID interno, pontes derivadas revisadas e evidências por campo, inclusive divergências |
| Completude | `person_data_coverage` | Fonte, área, período e estado de cobertura; zero importado não significa ausência de atividade |
| Formação e trajetória | `education`, `public_career_event` | Cursos e eventos com ano/data e fonte; primeiro mandato e início declarado da vida pública separados |
| Partido | `political_party`, `political_party_affiliation` | Partido e histórico com datas conhecidas e data de observação |
| Cargo | `institution`, `office_term`, `office_exercise` | Casa/cargo/UF, mandato e intervalos de exercício; suplentes e licenças |
| Proposição | `proposition`, `proposition_person`, `proposition_event` | Identificação por Casa, estado consolidado, autoria/coautoria/relatoria e tramitação |
| Voto | `voting`, `person_vote` | Resultado de cada deliberação e voto individual |
| Lei | `law`, `proposition_law` | Norma publicada e ligação documental às proposições que a originaram |
| Emenda | `budget_amendment`, `amendment_person`, `amendment_execution_snapshot` | Emenda, vínculo de autor/solicitante/apoiador e execução por recorte e data |
| Leitura | `person_profile` | Card de perfil materializado e pesquisável |

## Semântica que o produto deve respeitar

- **Cargo atual:** vem de `office_exercise`, nunca apenas da eleição ou da data prevista da legislatura. Intervalos usam início inclusivo e fim exclusivo. Ao normalizar uma fonte que registra último dia inclusivo, converter esse fim para o dia seguinte.
- **Partido:** o card traz o último partido observado válido e a data da observação; não inventa uma data histórica de filiação quando ela é desconhecida. A importação precisa reconciliar registros divergentes/antigos antes de publicar.
- **Formação:** escolaridade declarada é diferente de curso concluído. Guardar fontes em ambas.
- **Vida pública:** primeira candidatura, primeiro cargo e ingresso declarado são eventos distintos. Não preencher um usando outro sem evidência.
- **Projetos que aprovou/não aprovou:** exibir votos individuais sim/não, abstenção e demais situações. Resultado da votação é coletivo; um voto “não” pode ocorrer em proposta aprovada. Ausência de registro não pode ser convertida em voto contrário.
- **Autoria e resultado:** contagens de propostas aprovadas/rejeitadas referem-se à autoria/coautoria e ao estado consolidado na Casa. Não medem mérito nem participação em todas as votações. Aprovação de um requerimento ou destaque não deve atualizar automaticamente o resultado final da proposição.
- **Leis:** ter ligação com lei publicada é separado de ter uma proposta aprovada numa Casa. Uma mesma lei vinculada a várias propostas é contada uma vez por pessoa.
- **Emendas coletivas:** autoria formal, solicitação e apoio ficam separados. Não dividir ou atribuir todo o valor de uma emenda coletiva a cada apoiador.
- **Dinheiro:** valores são `numeric`, não float. Os snapshots são saldos por data e recorte, não movimentos para somar ao longo do tempo. Empenhado, liquidado e pago não são somados como um total único. NULL é desconhecido, não zero. Valores negativos podem representar ajustes na fonte; revisar a semântica por coletor.
- **Cobertura:** contagens no card são de registros importados. A interface só pode comunicar ausência de atividade quando o período/fonte estiver coberto. Exibir “cobertura parcial” ou “não disponível” conforme `data_coverage`.

## Recuperação otimizada

O card requer uma consulta por ID ou slug na `person_profile`, com índice único. Busca textual usa `tsvector` em português com índice GIN; filtro de UF usa array indexado por GIN; partido usa B-tree. A busca por texto atende termos/prefixos compatíveis com a pesquisa textual; não é autocomplete tolerante a erros. Similaridade/trigramas só depois de necessidade medida.

As listas de trabalhos continuam relacionais e paginadas. Os índices começam pela pessoa nas relações de autoria, voto e emenda. Usar paginação por cursor e buscar detalhes em lote, evitando uma consulta para cada item.

Os agregados do card são calculados independentemente antes do JOIN. Isso evita multiplicar contagens quando uma pessoa possui várias emendas, votos e propostas.

Complexidade aproximada: busca B-tree por pessoa/slug é O(log P); listagem indexada dos vínculos é O(log R + K), para R vínculos e K resultados. A projeção ocupa O(P + A), com P pessoas e A cargos/coberturas resumidos. O refresh examina os registros de origem e agrega/ordena grupos: custo linear nas leituras mais custos de agrupamento/ordenação; não pressupor O(1). Não há benchmark de carga de produção nesta etapa.

## Atualização e consistência

1. Importar/reconciliar registros na base canônica numa transação por lote, preservando evidências e versões.
2. Atualizar as coberturas efetivamente verificadas.
3. Após confirmar a transação, executar `REFRESH MATERIALIZED VIEW CONCURRENTLY se_liga_brasil.person_profile` fora da transação de ingestão, num job serializado.
4. Executar também refresh diário para alterações de cargo decorrentes da passagem da data. Monitorar `refreshed_at` e falhas. A migração não cria esse agendamento.

O índice único por pessoa permite refresh concorrente. A visão é criada inicialmente populada, ainda que sem pessoas. O leitor recebe o snapshot anterior enquanto o refresh ocorre. Nenhuma escrita canônica deve ser considerada imediatamente visível no card; o SLA de atualização será definido com os coletores.

Se o refresh integral ficar caro com milhões de votos, migrar os agregados para tabelas de projeção por pessoa com fila de pessoas afetadas, revisão/versão e upsert transacional. Não introduzir essa infraestrutura antes de medir duração e carga.

## Consultas de referência

Ver `db/queries.sql`: card por ID, busca, autoria paginada, voto individual, emendas e último snapshot de cada recorte, duração efetiva do cargo.

## Isolamento e acesso

Schema privado, RLS habilitada nas tabelas e nenhum acesso para `PUBLIC`, `anon` ou `authenticated`. A visão materializada não oferece RLS própria: sua proteção depende de grants e de permanecer privada. A futura API deve consultar com um papel de backend restrito a dados revisados ou uma camada de leitura explicitamente publicada; não colocar senha administrativa/service role no navegador.

Não usar o usuário administrativo compartilhado para a aplicação em produção. Criar papel dedicado e políticas/grants quando o fluxo de publicação for definido. Este SQL não expõe o schema no PostgREST nem altera as configurações da contabilidade. Schemas compartilham CPU, armazenamento, conexões e backups do projeto: isolamento lógico não é isolamento de infraestrutura.

## Pendências antes de ingestão real

- Instalação inicial concluída. Não reaplicar `schema.sql`; usar migrations evolutivas para alterações. A aplicação detecta schema existente antes de executar DDL.
- Criar migrations evolutivas após a instalação inicial; versionar cada mudança, sem `DROP ... CASCADE` de rotina.
- Implementar gravação de evidências append-only/auditoria e coletores idempotentes; o SQL conserva versões por hash, mas ainda não proíbe UPDATE de evidências pelo administrador.
- Resolver correspondência entre pessoas, mandatos e proposições das duas Casas; projetos transferidos podem ter IDs diferentes e devem conservar ambos, ligados por evidência.
- Validar filiações sobrepostas e intervalos de exercício incompatíveis no coletor. A duração de referência une intervalos sobrepostos para não duplicar dias; isso não torna um dado contraditório correto.
- Ingerir somente votos nominais quando houver associação individual pública; votação secreta/simbólica não deve gerar voto pessoal fictício.
- Padronizar chaves dos recortes financeiros e comprovar que não se sobrepõem antes de somar valores.
- Fazer EXPLAIN/benchmark com volume representativo e verificar grants no projeto remoto.

## Referências oficiais de implementação

- [PostgreSQL — schemas e privilégios](https://www.postgresql.org/docs/current/ddl-schemas.html).
- [PostgreSQL — visões materializadas](https://www.postgresql.org/docs/current/rules-materializedviews.html).
- [PostgreSQL — refresh concorrente](https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html).
- [Supabase — schemas personalizados e exposição na API](https://supabase.com/docs/guides/api/using-custom-schemas).
