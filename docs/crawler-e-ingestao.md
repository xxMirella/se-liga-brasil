# Crawler e ingestão auditável

## Decisão de implementação

O projeto usa Python. Cada diretório de `src/` representa um serviço ou biblioteca; não existe diretório agregador com o nome do projeto. Normalização e comparação de existência não conhecem o TSE. O conector eleitoral fornece regras de formato, chaves e projeções; a persistência trabalha com entidades genéricas identificadas por fonte + tipo + chave externa.

A implementação segue cinco fronteiras: descoberta do catálogo, aquisição de arquivos originais, validação/normalização, reconciliação com o banco e projeção relacional. As fases podem ser executadas separadamente para inspeção antes da ingestão. Não há automação periódica instalada.

## Abordagens de reconciliação

**Consultar registro por registro:** simples, mas exige n viagens ao banco e vira um gargalo de latência. A API `exists` serve para verificações pontuais, não para executar dentro do laço de um crawler.

**Chave única e `INSERT ... ON CONFLICT`:** evita duplicatas e protege contra concorrência. Sozinho, não informa se o conteúdo mudou, preserva histórico ou resolve identidade entre fontes.

**Chave única + hash normalizado + comparação em lotes — adotada:** a chave identifica o fato; o hash identifica o conteúdo. A consulta em lotes determina registros novos, iguais, alterados, antigos ou conflitantes. Metadados voláteis, como horário de coleta, não entram no hash. A gravação ainda usa constraints e UPSERT para garantir atomicidade. As versões anteriores ficam preservadas.

**Snapshots completos:** adequados para comparar a presença de itens em um arquivo, como bens declarados. Cada artefato mantém sua associação aos registros encontrados. Um bem ausente no snapshot atual não deve ser somado como se ainda estivesse presente. Também não deve ser interpretado automaticamente como venda. Arquivos incompletos/rejeitados não provam exclusão.

**CDC e eventos:** muito úteis quando a fonte disponibiliza um log de mudanças. O catálogo do TSE entrega arquivos, então o crawler compara snapshots; não existe acesso ao log interno do banco do TSE.

**IA ou comparação aproximada por nomes:** podem sugerir correspondências, mas não devem decidir sozinhas a identidade de uma pessoa ou a veracidade de fatos. A implementação usa identificadores oficiais e o histórico de candidaturas. Vínculos conflitantes são enviados à quarentena.

## API reutilizável de existência

```python
from datetime import UTC, datetime

from service.data_validation import DataExistenceService, RecordIdentity, RecordSnapshot
from database.record_lookup import PostgresRecordLookup

checker = DataExistenceService(PostgresRecordLookup(connection))
identity = RecordIdentity(
    source_code="camara",
    data_type="salary",
    external_key="deputy:123:2026-09",
)
exists = checker.exists(identity)
state = checker.inspect_record(
    RecordSnapshot(
        identity=identity,
        normalized_data={"gross": "1000.00", "month": "2026-09"},
        source_generated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
)
```

Este exemplo demonstra a API; não é um salário real nem um conector de salários implementado. Para carga em massa, usar `inspect_records` com um lote limitado ou `iter_record_states` com um iterável. A biblioteca retorna `new`, `unchanged`, `changed`, `stale` ou `conflicting`; uma consulta SQL parametrizada atende cada lote. Nunca aceita nome arbitrário de tabela interpolado em SQL. A mesma interface pode usar outro adaptador implementando `RecordLookup`.

O escopo da chave é obrigatório. Dois salários iguais de pessoas diferentes são fatos distintos; duas pessoas com o mesmo nome não são a mesma identidade. O hash não substitui a chave.

## Normalização reutilizável

`normalization` expõe `normalize_text`, `normalize_digits`, `normalize_date`, `normalize_money`, `normalize_boolean`, `normalize_timestamp` e `normalize_year`. As regras específicas do TSE ficam em `crawlers/tse/normalization.py`.

Identificadores permanecem como texto; não são convertidos a números que possam perder precisão ou zeros relevantes. Valores brasileiros são convertidos em strings decimais e gravados em `numeric(20,2)`, sem ponto flutuante binário. Datas impossíveis, textos com caracteres de controle, valores fora do intervalo e booleanos desconhecidos são rejeitados. Marcadores de ausência do TSE são tratados como ausência, não como zero.

As políticas de formato são explícitas: `normalize_money(..., decimal_separator=".")` aceita ponto decimal sem separador de milhar; o padrão aceita o formato brasileiro com vírgula. `normalize_date(..., date_format="%Y-%m-%d")` aceita datas ISO; `normalize_timestamp` exige fuso. No TSE, bens usam vírgula e o limite de campanha do complemento usa ponto; aceite de candidatura usa timestamp. Não há adivinhação de formato.

## Descoberta e downloads

Fonte: [catálogo oficial de candidatos do TSE](https://dadosabertos.tse.jus.br/dataset/candidatos-2026). A descoberta usa `package_show` e, para todos os anos, `package_search` da API CKAN. Ela registra o catálogo recebido e filtra recursos reconhecidos; os nomes dos arquivos não são inventados.

Recursos reconhecidos: candidatos, informações complementares, histórico de candidaturas, bens, propostas de governo e certidões criminais. A disponibilidade varia por ano. A seleção de recursos de documentos considera UF; arquivos CSV nacionais são filtrados linha a linha.

URLs e redirecionamentos são limitados a hosts oficiais conhecidos e HTTPS. Há timeout, tentativas limitadas para falhas transitórias, limites por arquivo e execução, e downloads em streaming. Arquivos parciais são removidos. O arquivo completo é armazenado pelo SHA-256 com escrita atômica. ETag/Last-Modified evitam download desnecessário, mas há nova verificação completa após o intervalo configurado. Um `304` só é aceito se a cópia local ainda existe e seu hash confere.

A pasta local usa permissões restritas e está fora do Git. O arquivo bruto pode conter campos pessoais não necessários ao portal; CPF, título eleitoral e e-mail não são transportados para registros normalizados nem logs. Não servir `data/` como diretório público.

## Validação e quarentena

A validação confere checksum, estrutura ZIP, limites de expansão, caminho de entradas, criptografia e links simbólicos. O CSV é lido em streaming, com Latin-1, separador `;` e colunas obrigatórias conhecidas. Alteração incompatível de cabeçalho ou duplicatas conflitantes impedem a ingestão do artefato inteiro. Linhas com valores inválidos entram em quarentena, enquanto linhas válidas podem ser ingeridas com status explícito `partial`.

Um índice SQLite local identifica duplicatas e guarda o recorte de candidatos para filtrar arquivos complementares que não contêm UF. Não é necessário carregar todo o cadastro na RAM. As saídas NDJSON só são publicadas após a leitura completa do arquivo. A ingestão verifica novamente os hashes do staging, do arquivo original e dos PDFs referenciados.

PDFs são armazenados como evidência opaca. O nome do arquivo associa ano/UF/sequencial à candidatura, e a assinatura básica `%PDF-` é conferida. Isso não comprova validade jurídica nem integridade semântica de um PDF; não há OCR, inferência sobre crimes ou leitura automática de conteúdo nesta versão. Documentos sem identidade reconhecível ficam em quarentena.

## Escrita, histórico e proveniência

Cada artefato é uma transação. Se uma gravação falhar, o artefato inteiro é revertido; outros artefatos previamente concluídos continuam registrados. A retomada pula artefatos concluídos, mas reavalia parciais, permitindo resolver vínculos ausentes após importar candidaturas.

`source_record` guarda fonte, URL, arquivo, conteúdo normalizado, momento de coleta e data de geração do dado. `ingestion_artifact` registra arquivo/hash/versão do parser/escopo e data da ingestão. `ingestion_entity` mantém o conteúdo atual; `ingestion_entity_version` mantém versões distintas; `ingestion_artifact_entity` registra a observação de cada entidade em um snapshot. Uma versão de conteúdo reaparecida reutiliza o conteúdo preservado, mas sua nova observação fica associada ao novo artefato.

Snapshots antigos não sobrescrevem a versão atual. Conteúdos diferentes com a mesma data de geração são preservados para auditoria e enviados à quarentena. Regras de exclusão automática ainda não existem: ausência em um arquivo não prova saída do cargo.

As projeções eleitorais são `electoral_candidacy`, `candidate_asset_declaration` e `candidate_document`. Dados complementares tratados ficam em entidades versionadas e `person_fact`, com evidência de declaração e revisão pendente. Não são classificados automaticamente como fatos biográficos verificados.

A identidade usa o sequencial do TSE no namespace do ano. O histórico oficial pode ligar um identificador antigo a uma pessoa já conhecida. Quando duas pessoas existentes entram em conflito com o vínculo, o crawler solicita revisão através da quarentena e não faz uma fusão destrutiva. Carregar eleições mais recentes antes das antigas ajuda a aproveitar os vínculos históricos.

O perfil eleitoral pode ser atualizado se sua fonte principal já é o TSE e o novo registro não pertence a uma eleição anterior. O crawler não sobrescreve um perfil cuja fonte principal é outra instituição. Candidatura não cria mandato nem exercício; partido da eleição fica na candidatura, sem substituir automaticamente filiação atual.

## Limites da fonte

O TSE permite acompanhar situação eleitoral, candidatura, resultado declarado, bens e documentos. **Não é a fonte de remuneração, saída efetiva de mandato, leis ou votações parlamentares.** Esses temas precisam de conectores das casas legislativas e portais de transparência. Situação de candidatura cassada ou substituída não equivale automaticamente a uma data de saída do exercício parlamentar. Proposta de governo também não equivale a proposição legislativa.

## Desempenho e revisão

Para n registros, b registros por lote e m entidades já armazenadas: leitura/normalização O(n), comparações por índices O(n log m) no caso típico e viagens SQL O(n/b), com uma quantidade fixa de statements por lote. Índices SQLite locais custam O(log n) por verificação e espaço O(n) em disco; RAM do fluxo é limitada a O(b), buffers e metadados do ZIP. A varredura não pode ser O(1), pois precisa ler n registros. A revisão cognitiva mede outra propriedade: facilidade de entender cada função.

O hook em `.codex/hooks.json` usa o formato nativo de hooks do Codex, confirmado na [documentação oficial](https://developers.openai.com/codex/hooks). Cobre `PostToolUse` para shell/edições e `Stop`. Não depende de Git nem de um diretório global de outra ferramenta; analisa todos os arquivos Python do projeto, excluindo dependências, dados e caches.

Limites estruturais iniciais: 60 linhas por função, pontuação cognitiva própria até 15 e aninhamento de controle até 3. O hook também identifica nomes de funções excessivamente genéricos e imports de infraestrutura em módulos de regras puras. Essa pontuação é uma heurística documentada, não a implementação completa de Cognitive Complexity da Sonar. Ela não prova responsabilidade única, correção ou Big O; o hook injeta a exigência de revisão semântica pelo agente. Ruff e pytest complementam o processo.

O evento `Stop` retorna uma solicitação de continuação se existem achados. Para ativação automática, o projeto precisa estar aberto como raiz no Codex e hooks de projeto devem estar habilitados/confiados pelas configurações do cliente. Não alterar silenciosamente os hooks globais. O script pode ser testado manualmente, e `se-liga-brasil review` executa a mesma análise sem depender do ciclo de hooks.

## Referências técnicas

- [CKAN Action API](https://docs.ckan.org/en/latest/api/index.html): catálogo e descoberta.
- [PostgreSQL INSERT/ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html): constraints e UPSERT.
- [RLS no Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security): schema privado e defesa adicional.

## Verificação executada em 6 de outubro de 2026

A extensão foi aplicada ao schema privado: 32 tabelas, todas com RLS e sem acesso dos papéis públicos da API. A ingestão piloto usou arquivos nacionais de 2026 filtrados para PA: 741 candidaturas atuais, 1.938 registros de histórico, 741 complementos e 2.517 declarações de bens. Houve 32 rejeições de vínculo histórico sem identidade segura; o lote ficou explicitamente `partial`. As versões rejeitadas permanecem auditáveis e não forçam fusão de pessoas. Documentos de todas as UFs e eleições históricas completas ainda não foram ingeridos nesse piloto.
