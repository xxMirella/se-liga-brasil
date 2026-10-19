# Votações do Senado e arquitetura analítica

Pesquisa em 17/10/2026, com fontes oficiais e amostras pequenas da API. Este documento propõe modelagem e armazenamento; não aplica migração, não ingere votos no PostgreSQL e não substitui os serviços existentes. Os arquivos originais permanecem imutáveis. Casos concretos foram usados para validar o contrato, sem documentar nomes de pessoas.

## Recomendação

Manter **PostgreSQL como banco canônico da aplicação** e acrescentar **Parquet + DuckDB local para processamento analítico em lotes**. O volume de votações, isoladamente, não justifica abandonar relações, chaves estrangeiras e transações. O problema atual é principalmente cobertura e semântica: a auditoria anterior encontrou tabelas de votação e votos vazias, embora o esquema já represente essas relações.

DuckDB é software livre sob licença MIT, funciona integrado ao processo Python e admite persistência em disco. Não exige contratar um servidor analítico. Isso não torna disco, backup, energia ou hospedagem ilimitados: a proposta usa recursos locais existentes e deve medir seu consumo. [Documentação e licença do DuckDB](https://duckdb.org/faq).

Parquet conserva datasets colunares comprimidos; DuckDB consegue selecionar colunas e aplicar filtros durante a leitura. Isso reduz leitura desnecessária, mas não elimina o custo de processar registros relevantes. [Leitura e escrita de Parquet](https://duckdb.org/docs/lts/data/parquet/overview).

## Fontes de votação

1. **API atual do Senado:** contrato OpenAPI em `https://legis.senado.leg.br/dadosabertos/v3/api-docs`, consultável pela [interface Swagger oficial](https://legis.senado.leg.br/dadosabertos/). O recurso `/dadosabertos/votacao`, versão 2, admite período em `AAAA-MM-DD`, identificação da proposição, sessão e processo. Preferir partições compartilhadas por período para não consultar a mesma votação para cada pessoa.
2. **Votações nas comissões:** recursos `/dadosabertos/votacaoComissao/comissao/{siglaComissao}` e `/dadosabertos/votacaoComissao/materia/{sigla}/{numero}/{ano}`, versão 1. As datas desse contrato usam `AAAAMMDD`, diferentemente do recurso anterior. Reunião, comissão e objeto votado precisam permanecer identificados. Resposta sem lista não prova inexistência de deliberação.
3. **Portal de votações nominais:** permite consulta por matéria, pessoa e período. Serve para conferir o voto publicado e acessar listas/mapas oficiais. O próprio portal limita sua finalidade às votações ostensivas com votos cadastrados individualmente. [Portal oficial](https://www25.senado.leg.br/web/atividade/votacoes-nominais).
4. **Tramitação, reuniões, atas e Diários:** necessárias para compreender aprovação de parecer, emendas, destaques, calendário, votação simbólica e norma produzida. Notícias oficiais ajudam a localizar eventos, mas não substituem a lista nominal completa. [Catálogo oficial de votações plenárias](https://www12.senado.leg.br/dados-abertos/legislativo/plenario/votacoes-nominais/info/webservice-de-votacoes-nominais-por-data-da-sessao-plenaria).

A documentação atual marca os antigos endpoints `plenario/votacao/nominal/{ano}` e `plenario/lista/votacao/...` como depreciados. Não construir a nova integração exclusivamente sobre eles. Não foi comprovado o primeiro ano integralmente disponível nem cobertura completa das comissões: cada partição precisa de sua própria avaliação.

### Validação do tema da escala de trabalho

O assunto possui propostas diferentes. Uma busca temática não pode fundi-las nem transferir votos de uma para outra.

- **PEC 148/2015:** a página oficial consultada mostra parecer aprovado na CCJ em 10/12/2025 e situação de pronta para deliberação plenária. O [item da 45ª reunião da CCJ](https://legis.senado.leg.br/atividade/comissoes/comissao/34/reuniao/14323/item/106659) comprova aprovação do parecer com três emendas. A consulta de comissão correspondente retornou somente metadados, sem votos individuais; não foi obtida lista nominal completa desse evento. A aprovação do parecer não autoriza criar 81 votos favoráveis nem declarar aprovação final da PEC. [Tramitação da PEC 148/2015](https://www25.senado.leg.br/web/atividade/materias/-/materia/124067).
- **PEC 221/2019:** a notícia oficial de 02/09/2026 descreve votação **simbólica** na CCJ, com manifestações contrárias. Não transformar presença em voto individual ou deduzir uma lista completa por subtração. [Notícia da deliberação na CCJ](https://www12.senado.leg.br/noticias/materias/2026/09/02/aguardar-fim-da-escala-6x1-passa-na-ccj-e-vai-a-plenario?trk=public_post_comment-text).
- Para essa segunda proposição, há **duas votações nominais plenárias em 14/10/2026**, uma por turno. A [página nominal oficial](https://www25.senado.leg.br/web/atividade/materias/-/materia/174386/votacoes) publica 75 votos favoráveis e um contrário em cada turno. O [registro de tramitação](https://www25.senado.leg.br/web/atividade/materias/-/materia/174386) informa promulgação em 16/10/2026 e transformação na Emenda Constitucional nº 141/2026. Não generalizar esse desfecho à PEC anterior.

Consulta pequena efetivamente executada:

```text
https://legis.senado.leg.br/dadosabertos/votacao.json?sigla=PEC&numero=221&ano=2019&dataInicio=2026-10-14&dataFim=2026-10-14&v=2
```

Retornou `idProcesso=9056435`, `codigoMateria=174386`, `codigoSessao=591267`, com `codigoSessaoVotacao=7106` no primeiro turno e `7107` no segundo. São identificadores de processos/eventos, não identificadores canônicos de pessoas. Os mapas oficiais vinculados pelo portal são:

```text
https://legis.senado.leg.br/parlam-servicosweb/api/v1/relatorios/mapa-votacao/materia/174386/votacao/7106/ordenacao/nome
https://legis.senado.leg.br/parlam-servicosweb/api/v1/relatorios/mapa-votacao/materia/174386/votacao/7107/ordenacao/nome
```

A inspeção desta pesquisa confirmou a tabela HTML e o JSON; os mapas binários acima não foram analisados. Em cada objeto JSON há **81 registros**, distribuídos em 75 `Sim`, um `Não`, um presidente, dois `P-NRV`, um `AP` e um `NCom`. Os campos de totais numéricos da API estavam nulos. O total de 77 publicado pelo portal corresponde a 75 + 1 + presidente; não corresponde à quantidade de linhas listadas.

Existe divergência pontual entre HTML e API: uma pessoa aparece como não comparecimento no portal e como presença sem voto registrado no JSON, nos dois turnos. Esses estados precisam de revisão; não são votos contrários. Mesmo com totais favoráveis/contrários concordantes, não declarar todas as observações individuais conciliadas. O serviço deve preservar evidências conflitantes e não escolher silenciosamente a última fonte lida.

Consulta de comissão executada, sem lista nominal na resposta:

```text
https://legis.senado.leg.br/dadosabertos/votacaoComissao/materia/PEC/148/2015.json?comissao=CCJ&dataInicio=20251210&dataFim=20251210&v=1
```

A consulta pública de opinião exibida na página de uma matéria é participação cidadã. Seus números de sim/não não são votos parlamentares e não podem alimentar `person_vote`.

## Revisão do modelo atual

O projeto já tem `proposition`, `proposition_person`, `proposition_event`, `voting`, `person_vote`, `law` e `proposition_law`. Reutilizar essas entidades. `voting` já diferencia modalidade e resultado; `person_vote` tem chave `(voting_id, person_id)`. Isso evita criar uma votação repetida para cada parlamentar.

São necessárias extensões compatíveis, mediante migração posterior:

- **Unidade de deliberação:** uma linha por votação específica, com instituição, órgão/colegiado, sessão/reunião, sequência, turno, etapa, objeto votado e proposição relacionada. Votar emenda, parecer, requerimento, destaque e texto principal são fatos distintos. A chave técnica do evento pode ser persistida; pessoa é sempre vinculada por `person_id` interno.
- **Objeto e efeito:** `subject_kind`, `subject_proposition_id` quando aplicável, `round_number`, `stage`, `legislative_body_id` e resultado coletivo. A aprovação de requerimento que acelera a tramitação não muda automaticamente o status do texto principal para aprovado. Não extrair resultado final apenas de palavras em descrição livre.
- **Tempo:** data do evento, precisão disponível, observação da fonte e ingestão separadas. A API examinada fornece dia, sem horário da votação; o `held_at` obrigatório atual não deve induzir horário fictício. Avaliar `held_on` e precisão explícita, preservando timestamps comprovados quando existentes.
- **Estado individual:** separar escolha (`yes`, `no`, `abstention`, `obstruction`) de situação (`presiding`, `absent`, `not_recorded`, `parliamentary_activity`, `excused`, `unknown`) e justificativa, conforme termos efetivamente publicados. O CHECK atual não contempla presidência e atividade parlamentar. Não perder essa informação convertendo tudo em ausência; nem tratar ausência como voto não.
- **Sigilo e votação simbólica:** modalidade e disponibilidade nominal são propriedades da votação. Não inventar votos individuais para votação secreta/simbólica. Manifestação de voto publicada em ata é evidência individual específica com modalidade/origem preservada, não mapa nominal completo presumido.
- **Partido no evento:** quando publicado, guardar como observação contextual da votação. Esse partido não substitui filiação atual e não comprova data exata de entrada ou saída.

O normalizador recém-criado em `src/crawlers/senado/legislative.py` é um início: coleta partição de até 31 dias, preserva descrição, resultado bruto, votos e totais, e não infere desfecho final. Ainda não projeta voto nominal no banco, não resolve identidade de todos os votantes, não coleta comissões nem separa turno/órgão/horário com contrato completo. `casaSessao='SF'` identifica a casa, não o colegiado; o `informeLegislativo` da amostra informa separadamente o Plenário. Essas distinções precisam entrar no contrato antes de declarar integração concluída.

### Identidade e retificações

O código pessoal do provedor permanece apenas no arquivo original e no contexto transitório de leitura. Construir em lote a correspondência com pessoas internas usando dados pessoais e evidências já validadas; não adicionar `person_identifier` com IDs externos. Nome parlamentar e partido, isoladamente, não identificam pessoa com segurança. Quando faltarem nome completo/documento/nascimento ou correspondência revisada suficiente, preservar o fato bruto e deixar a vinculação pendente, sem atribuição automática.

Reutilizar `source_record` e hashes dos artefatos. Para cada votação/voto, manter uma projeção corrente e registrar somente revisões efetivas de conteúdo, com hash, versão do normalizador, observação, motivo e evidência. Releitura idêntica não cria outra versão. Retificação não equivale a um novo voto ou mudança política posterior: é uma revisão do mesmo fato. SCD tipo 2 pode representar versões conhecidas do registro, distinguindo tempo do evento e intervalo em que a base considerou cada versão válida. Não duplicar snapshots inteiros a cada execução.

## Repositório local e datasets

Fluxo proposto, sem arquivos de origem atendendo requisições públicas:

```text
Fontes oficiais → artefatos originais imutáveis
              → normalização/validação/identidade em lotes
              → Parquet derivado + manifestos de partições
              → DuckDB para cruzamentos e validações analíticas
              → transação de publicação no PostgreSQL
              → API pública → linha do tempo
```

A aplicação consulta tabelas relacionais e, quando medição justificar, projeções materializadas. Não abre CSV, JSON, PDF ou Parquet original por visita de perfil. A proveniência é preservada no sistema; a resposta pública recebe fatos e links oficiais adequados, sem depender de caminhos locais.

Estrutura sugerida: `data/derived/legislative/{institution}/{dataset}/year=AAAA/`. Guardar o original uma vez; derivados identificados por hash/versão. Evitar partição por pessoa, que multiplica arquivos pequenos e repete eventos compartilhados. O manifesto registra intervalo, estado, schema, hash de entradas, hash do derivado, quantidade de linhas e término da paginação. Não tratar ano do nome do diretório como prova de cobertura integral.

Datasets mínimos, com granularidade explícita:

1. **`votings`:** uma votação específica, incluindo órgão/turno/objeto/modalidade/resultado.
2. **`person_votes`:** uma observação individual por votação e pessoa identificada; escolhas e situações separadas.
3. **`proposition_authorship`:** pessoa + proposição + papel comprovado; coautoria e relatoria não viram autoria principal.
4. **`proposition_events`:** tramitações e decisões, mantendo o objeto e o efeito.
5. **`legislation_links`:** vínculo oficial entre proposição e norma; publicação e vigência não confundidas.
6. **`career_timeline`:** projeção derivada de fatos canônicos por pessoa/cargo/instituição/data; não uma segunda cópia de todos os documentos.
7. **`coverage`:** instituição + domínio + intervalo + atualização + integridade da coleta; inclui falta de dados e indisponibilidade nominal como estados próprios.

Versionar código, contratos e manifestos pequenos no repositório do projeto. Guardar arquivos volumosos fora do Git comum, em diretório local com backup independente. O [repositório oficial do DuckDB](https://github.com/duckdb/duckdb) fornece o motor gratuito, não hospedagem gratuita ilimitada dos nossos dados. Nenhum serviço cloud gratuito é requisito para esta primeira etapa. Publicação externa de datasets exige recorte próprio; não incluir documentos pessoais ou mapas internos de identificação.

## Alternativas e critérios de decisão

**Somente PostgreSQL:** menor mudança inicial e suficiente para ingestão canônica e páginas por pessoa. Usar consultas paginadas, lotes e índices antes de considerar outro motor. Arquivos brutos volumosos não precisam estar todos em JSONB no banco transacional.

**PostgreSQL + DuckDB/Parquet:** escolha recomendada para análise histórica local, geração reproduzível de datasets e carga incremental no banco atual. Coordenar um escritor por dataset e publicar partições concluídas atomicamente; não transformar o arquivo DuckDB compartilhado em banco multiworker de gravação sem avaliar o modelo de concorrência.

**SQLite:** útil para catálogo portátil ou ferramentas locais com escrita limitada. Não traz uma vantagem suficiente para substituir PostgreSQL e, como segundo motor linha a linha, não atende tão diretamente a análise colunar dos arquivos. [Usos apropriados e limites de concorrência](https://www.sqlite.org/whentouse.html).

**ClickHouse:** pertinente se medições revelarem agregações analíticas grandes e concorrentes que excedam o processamento local. Acrescenta servidor, operação e sincronização; distribuição gratuita do software não significa serviço cloud gratuito contínuo. Não introduzir agora sem volume, latência e concorrência medidos. [Arquitetura e finalidade analítica oficiais](https://clickhouse.com/docs/get-started/about/intro).

**Banco de grafos:** relações pessoa–proposição–votação–norma cabem no esquema atual. Só avaliar outra base se consultas com percursos variáveis e profundos forem requisito demonstrado. Linha do tempo e filtros por cargo não exigem, por si, um grafo.

## Desempenho e modularidade

Reutilizar aquisição, cache, cooldown, locks de fonte, ingestão e identidade existentes. Separar funções pequenas para planejamento de partições, leitura da fonte, normalização do evento, normalização do voto, resolução de identidade, validação cruzada e publicação. Extração e regras de domínio não consultam banco/rede por pessoa dentro do loop.

Uma partição serve a todas as pessoas interessadas; o orquestrador deduplica o recurso e distribui o resultado. Priorizar dados recentes e processos ativos; histórico encerrado usa checkpoints e revalidação menos frequente, com retificações ainda possíveis. Respeitar limites e `Retry-After` da fonte; não considerar uma resposta incompleta como partição concluída.

A leitura e validação de n votos custam O(n). Mapa em memória de identidades custa O(p) para p pessoas e oferece busca esperada O(1) por registro; isso não torna a ingestão total O(1). Memória de processamento deve ser limitada por lote. Ordenação global pode custar O(n log n); evitar repetição por pessoa. Para páginas, índices adequados e cursor dão custo aproximado O(log n + k) para k itens, não O(1).

No PostgreSQL, revisar planos e índices por padrão real de consulta. Um índice em `person_vote(person_id, voting_id)` complementa a chave atual iniciada por votação. A consulta cronológica pode usar `voting(held_at DESC, id DESC)` ou uma projeção por pessoa/data quando o join for medidamente caro. Não prometer que índices separados eliminam ordenação entre tabelas. [Índices multicoluna](https://www.postgresql.org/docs/current/indexes-multicolumn.html).

## Caminho incremental e aceite

1. Consolidar contratos de votação e estados individuais, incluindo casos simbólico, secreto, presidente, presença sem voto e divergência entre fontes.
2. Projetar uma partição pequena em schema de teste, identificando pessoas e preservando dois turnos como dois eventos. Reexecutar e comprovar idempotência.
3. Implementar leitura de comissões separadamente; registrar indisponibilidade de nominal sem gerar buscas infinitas.
4. Expandir o serviço de cobertura por instituição/domínio/período, reutilizando fila e orquestrador. Uma pessoa vinculada a uma proposição não tem automaticamente histórico legislativo completo.
5. Medir bytes, memória, tempo de parsing, número de requisições e tempo de publicação; só então definir retenção e particionamento mais finos.
6. Publicar fatos validados nas tabelas atuais e estender a API da linha do tempo com filtro por cargo, órgão, período, objeto e escolha de voto.

A interface deve permitir abrir a votação, ver cada turno e o texto/objeto votado. Quantidade de votos, projetos ou leis não é avaliação automática de qualidade ou evolução política. Exibir atribuições do cargo, período de exercício e cobertura ao lado das atividades comprovadas; lacuna de fonte não equivale a inatividade.
