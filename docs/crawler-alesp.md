# Crawler ALESP: catálogo e remuneração publicada

## Escopo implementado

O adaptador fica em `src/crawlers/alesp/`. O catálogo oficial foi investigado e
amostras foram preservadas em `data/alesp/research`, com URLs, SHA-256 e horário
UTC no manifesto. O catálogo contém dados parlamentares, administrativos,
legislativos, normas e agenda. O inventário detalhado está em
`data/alesp/research/README.md`.

A primeira projeção implementada é a folha mensal dos deputados estaduais,
publicada em https://www.al.sp.gov.br/alesp/folha-de-pagamento-deputados/ .
O crawler descobre os links publicados; não inventa competências futuras.
Em 16/10/2026 o índice tinha 11 competências, de outubro/2025 a agosto/2026:
1.039 registros, com 98 em dezembro, 95 em maio e 94 nos demais meses.
Todos os arquivos foram baixados e validados localmente. Não se pressupõe que
94 seja um limite fixo, pois substituições podem mudar o número de pessoas.

## Contrato e semântica

A tabela HTML `dados` contém quatro células por registro: nome completo
publicado, remuneração bruta, tributos e remuneração líquida. O cabeçalho pode
usar `td` e está em outra tabela. A competência declarada no documento deve
coincidir com o link. Março/2026 foi publicado em Latin-1; os demais arquivos
examinados são UTF-8, apesar de metadados que podem indicar outro charset.

Bruto já considera ausências dedutíveis; tributos agregam IR e contribuição
previdenciária. A fonte não fornece as duas parcelas tributárias separadas,
rubricas de desconto, data do pagamento, número da folha, décimo terceiro ou
identificador de folha complementar. `payroll_kind=published_monthly_aggregate`
expressa esse limite. Não converter o bruto em subsídio legal ou inventar rubricas.

A normalização usa decimais exatos e exige bruto - tributos = líquido. Zero e
valores negativos são preservados: dezembro/2025 contém uma linha negativa.
O sinal não explica sozinho o motivo do lançamento. Marcadores de ausência
são específicos da fonte; `-1` numérico ALESP não é sentinela de ausência TSE.

## Reutilização e responsabilidades

- `service/acquisition`: transporte HTTPS com hosts autorizados, redirects
  restritos, retries, limites por arquivo/execução, cache e arquivos imutáveis.
- `service/crawling`: lock local, downloads, fases, ingestão em lotes e ciclo
  de execução com status/logs. O pipeline TSE continua específico onde exige
  índice de candidaturas e validação entre recursos.
- `service/ingestion`: reconciliação genérica por fonte + tipo + chave,
  transações, checksums, versões e projeção injetável. A versão esperada do
  parser agora é parâmetro; ALESP não precisa fingir ser TSE.
- `storage`: gravação privada/atômica, hashes, NDJSON e manifestos de staging.
- `parsing/html`: extração de links/tabelas e decodificação sem I/O de rede.
- `normalization`: nomes, Unicode e valores monetários com política por fonte.
- `crawlers/alesp`: URLs, descoberta, contrato da folha, normalização e estratégia
  de projeção; não contém lógica eleitoral do TSE.

Tempo de processamento O(n) sobre os registros; memória O(m + b), onde m é o
número de linhas de uma folha limitada em bytes e b é o lote de ingestão. Não
há consulta remota por linha. A associação por identificador é feita em JOIN.

## Modelo persistido

`se_liga_brasil.person_payroll_payment` guarda competência (primeiro dia do mês),
órgão, cargo informado pelo contexto da publicação, UF, moeda, bruto, tributos,
líquido, nome/chave do destinatário, origem, instante observado e identidade.
`office_exercise_id` é opcional: a folha não comprova as datas do exercício.

A chave natural desta fonte usa competência + hash do nome completo normalizado.
É uma chave do destinatário **na publicação**, não identidade global de pessoa.
Mudanças de nome exigem resolução; nomes iguais dentro do mesmo mês bloqueiam
a publicação para evitar consolidação indevida.

A tabela é projeção atual; `ingestion_entity_version` e `source_record` preservam
o histórico imutável com hash, payload, origem e artefato. Conteúdo idêntico
não abre versão. Correções observadas mais tarde atualizam a projeção e abrem
versão; dados antigos não sobrescrevem novos, e divergências no mesmo instante
são rejeitadas. Cada artefato é transacional. A fonte não informa timestamp de
publicação: `timestampBasis=collected_at` sinaliza que a ordem é de observação,
sem atribuir essa data à competência ou ao fato administrativo.

## Associação com pessoa

A folha não fornece CPF, matrícula nem ID parlamentar. A resolução combina a folha com o XML oficial, perfis na API `legis-api-portal-prd.al.sp.gov.br/parlamentar-portal/detalhes/{matricula}` e o diretório oficial de gabinetes. IDs de unidade administrativa podem ser reutilizados e não constituem identidade permanente.

Os pagamentos inicialmente sem ligação comprovada ficam com `person_id=NULL` e `identity_status=pending`. O resolvedor usa evidências, bloqueia ambiguidades e registra a ponte em `person_identifier`, no namespace derivado `payroll_recipient`. Não cria pessoas. As exceções exigem evidências pessoais revisadas com guardas de fonte e destino; divergências de nascimento não são corrigidas automaticamente.

O comando `resolve-identities` atualiza pagamentos previamente ingeridos com evidência e auditoria, inclusive quando os artefatos de pagamento já estão concluídos. A resolução também integra o fluxo de ingestão ALESP. A cobertura de identidade é exibida separadamente; a estrutura permanece privada, com RLS e sem exposição ao Data API.

## Execução

Na raiz do projeto:

```bash
.venv/bin/se-liga-brasil --source alesp discover
.venv/bin/se-liga-brasil --source alesp download
.venv/bin/se-liga-brasil --source alesp validate
.venv/bin/se-liga-brasil db-migrate --env-file /caminho/privado/.env
.venv/bin/se-liga-brasil --source alesp ingest --env-file /caminho/privado/.env
.venv/bin/se-liga-brasil --source alesp run --months 2026-08 --env-file /caminho/privado/.env
```

Sem `--years`/`--months`, processa todas as competências efetivamente publicadas.
Fases offline respeitam o mesmo recorte. `download` pode ser executado novamente
para retomar: arquivos íntegros e recentes são reutilizados. Após 24 horas,
revalida a fonte para descobrir correções; arquivos modificados mantêm versões.
Configuração: `config/alesp-crawler.json`. Logs e planos: `data/alesp`.

## Outras fontes catalogadas

O XML de deputados permite observar partido e situação no momento da coleta,
mas não informa entrada/saída de filiação. Catálogos oficiais incluem despesas
de gabinete, funcionários/cargos/lotações, proposições/autores/comissões,
votos/presenças, normas e agenda. Amostras e páginas do catálogo foram baixadas
para pesquisa; não se fez uma cópia integral de todos os grandes conjuntos.
Eles demandam adaptadores próprios e definição de escopo antes da ingestão.

## Conexão Supabase e locks

O crawler usa locks advisory de sessão. Se a configuração indicar o pooler
Supabase transacional na porta 6543, o adaptador usa o mesmo host/credenciais
na porta 5432 (modo sessão), sem alterar o arquivo de ambiente. Prepared
statements automáticos ficam desativados (`prepare_threshold=None`) para
evitar colisões de estado do pool. Conexões PostgreSQL diretas permanecem no
endereço configurado. Referências oficiais:
https://supabase.com/docs/guides/database/connecting-to-postgres e
https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL .

## Resultado verificado em 2026-10-16

A resolução de identidades confirmou os 1.039 pagamentos publicados, correspondentes a 100 destinatários, sem pendências. A associação usa identificadores estáveis da pessoa e evidências das fontes; partido não compõe uma chave permanente. Cinco exceções têm crosswalk explicitamente revisado em `config/alesp-reviewed-identities.json`; divergências de aniversário são preservadas para revisão e não alteram a data de nascimento da pessoa.

O comando disponível é `se-liga-brasil --source alesp resolve-identities --env-file /caminho/privado/.env`. Ele também é executado após a ingestão ALESP. A coleta das evidências revisadas deduplica URLs antes da aquisição. Consulte `docs/cognitive-code-review.md` para a análise de complexidade e as limitações da revisão incremental.
