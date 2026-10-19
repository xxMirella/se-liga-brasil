# Identidade, partido e contexto temporal

A pessoa possui um UUID estável. Partido, candidatura e cargo descrevem vínculos e
contextos; uma mudança de partido não gera outra pessoa.

## Resolução de identidade

1. CPF válido: normalização de formato, verificação dos dígitos e fingerprint HMAC-SHA256.
2. Identificador oficial de candidatura: fonte, ano e SQ_CANDIDATO.
3. Histórico oficial: a ligação ANO_ELEICAO_ATUAL/SQ_CANDIDATO_ATUAL pode unificar
   cadastros provisórios, com auditoria em `person_identity_alias`.
4. Nome normalizado, nascimento e partido: sugerem revisão em `person_identity_review`;
   não autorizam a união automática de homônimos sem uma chave forte.

CPFs diferentes ou nascimentos incompatíveis impedem união. Conflitos de relações
também impedem união: a operação retorna um motivo específico e reverte alterações.
CPF ausente ou inválido permite cadastro pela chave TSE, mas não participa do matching
por documento. Valores inválidos ficam sinalizados para revisão, sem guardar o CPF no log.

O CPF em texto não entra em payloads normalizados. A evidência separada contém apenas
fingerprint e status. A chave HMAC permanece em `data/private/identity.key` (600), ou
vem de `SE_LIGA_BRASIL_IDENTITY_KEY`, com pelo menos 32 bytes. Backups e réplicas devem
preservar a mesma chave; não trocar essa chave para uma base existente sem migração.
Arquivos brutos oficiais continuam privados em `data/tse/archives` e contêm os dados
publicados pelo TSE. Não publicar arquivos brutos, fingerprints ou chave de identidade.

O parser v3 reprocessa arquivos das versões anteriores e inclui o contexto de diagnóstico. A evidência de identidade não altera
o hash dos campos de negócio, evitando conflito artificial na mesma data de geração.

## Partidos e validade

`political_party` registra o código eleitoral e o último nome/sigla observado no contexto
mais recente. Os registros de origem preservam os dados recebidos e sua proveniência.
O cadastro por código do TSE não é uma verificação cadastral adicional
no SGIP nem uma afirmação de continuidade jurídica entre partidos que reutilizem números.

Toda candidatura validada exige código, nome e sigla do partido. `electoral_candidacy`
possui FKs para partido e observação de filiação.

`political_party_affiliation` mantém:

- `information_valid_from` / `information_valid_until`: período de validade da informação
  observada; fim exclusivo, encerrado pela próxima observação daquele contexto.
- `election_context_year` / `information_scope`: separa eleições. Um histórico de 2018
  publicado hoje não encerra nem substitui a informação de 2026.
- `recorded_at`, `source_record_id`, `evidence_kind`: quando e de onde veio a informação.
- `valid_from` / `valid_until`: datas reais de filiação/desfiliação, somente quando uma
  fonte apropriada as informar. Permanecem NULL para a declaração eleitoral do TSE.

O rótulo `electoral_declaration` significa partido informado na candidatura, não uma
certificação de filiação atual no FILIA. O perfil escolhe o último contexto eleitoral
disponível e os dados anteriores permanecem associados aos seus partidos originais.

## Trabalhos, bens, documentos e notícias

`person_activity_context` relaciona cada versão de um registro à pessoa, ao partido,
à observação de filiação e à candidatura ou mandato pertinente. Bens e complementos
usam ano + SQ_CANDIDATO; preservam o contexto de partido/cargo daquela candidatura.
Um cargo pretendido não vira mandato ou exercício comprovado.

`service/activity_context` fornece uma API reutilizável, com adaptador em
`database/activity_context.py`, para futuros conectores de propostas, notícias e trabalhos.
Ela confere propriedade da filiação e do mandato, fonte do registro e datas. Para afirmar
filiação em uma data de atividade, exige período real comprovado; snapshots eleitorais
isolados não atendem a essa exigência. Notícias e trabalhos ainda precisam de seus crawlers.

As chaves únicas tornam repetição de documento, candidatura, filiação e contexto idempotente.
Os lotes usam SQL e pipeline PostgreSQL; sem consulta remota por pessoa. A varredura de n
registros é O(n), com RAM limitada ao lote e índices em disco. Uniões raras usam operações
relacionais indexadas e lock transacional para impedir resolução concorrente incompatível.

## Carga restrita a SP e RJ

```sh
.venv/bin/se-liga-brasil run --years 2026,2022,2018 --ufs SP,RJ --office-codes 5,6,7 --kinds candidate,history,complement,asset --env-file /home/mirella/projetos/mdqc-knowledge-center/.env
```

Código 5: senador; 6: deputado federal; 7: deputado estadual. O histórico pode apresentar
outros cargos anteriores dessas pessoas, mas o recorte por UF é estrito: referência atual
e candidatura histórica precisam estar em SP/RJ. Eleições/cargos não publicados na fonte
não são fabricados. Dados eleitorais não substituem a lista de parlamentares em exercício.

A limpeza solicitada ficou limitada ao schema `se_liga_brasil`; CSVs de recuperação,
com manifest de contagens, ficam em `data/backups/20261007T165428Z/`. Schemas contábeis
não foram alterados. Nunca executar reset automaticamente ao iniciar o crawler.

## Diagnóstico e encerramento do crawler

O parser v3 inclui nos logs de rejeição o nome público disponível, ano eleitoral,
`SQ_CANDIDATO`, UF, partido, cargo, arquivo e linha CSV (incluindo o cabeçalho).
`context.candidate_source` aponta o arquivo e a linha da candidatura usada na associação;
em bens e complementos, o nome pode ser recuperado do índice local de candidaturas.
Não são registrados CPF nem fingerprints. As informações adicionais usam uma lista
explícita de campos, sem despejar a linha bruta no log.

`CANDIDATE_IDENTITY_NOT_FOUND` significa que a chave oficial ano + `SQ_CANDIDATO`
não encontrou uma pessoa na projeção. Confira a candidatura em `candidate_source` e
suas rejeições anteriores: bens e complementos podem falhar como consequência de uma
candidatura rejeitada. Quando a fonte não fornece nome e não há candidatura no índice,
o diagnóstico identifica a pessoa pela chave oficial, sem inventar um nome.

Na análise da rodada de 7 de outubro, os valores “Não divulgável” causavam rejeição
booleana; agora representam informação desconhecida (`NULL`), sem virar `False`.
Uma divergência de nascimento com CPF já validado e vinculado gera revisão em
`person_identity_review`, preservando a associação pelo documento. Conflitos entre
CPFs diferentes, associações históricas ambíguas e divergências sem confirmação por
CPF continuam bloqueados. Valores negativos declarados para bens continuam rejeitados
pela regra atual de domínio; não são convertidos automaticamente em valores positivos.

O resumo terminal persiste após a tela de progresso e informa arquivos processados,
registros aceitos, rejeitados, falhas e caminho do log. O total aceito considera os
registros que passaram pela projeção, não os que apenas chegaram ao staging.
Só uma carga sem rejeições/falhas anuncia conclusão completa (código de saída 0).
Cargas parciais exibem “FINALIZADO COM PENDÊNCIAS” e retornam código de saída 1.
A reconciliação permanece em lotes, com passagem O(n) sobre os registros e memória
O(b) para o tamanho do lote; os diagnósticos usam um índice SQLite local em disco,
sem consulta remota por registro.
