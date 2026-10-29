# Otimização das requisições públicas (28/10/2026)

## Como foi medido

- Rotas estáticas e do painel: aplicação WSGI em processo (`PublicPortalWSGI`), mediana de 15 chamadas, com `Accept-Encoding: gzip`.
- Banco: cluster PostgreSQL descartável e local (initdb em diretório temporário, sem tocar na produção), schema das migrações do projeto e a pessoa fictícia dos testes de integração. Um proxy de conexão contou conexões e instruções por requisição.
- Tempos locais são pequenos (0,01 a 8 ms) porque não há latência de rede. Em produção o custo dominante são as idas e voltas ao PostgreSQL (RTT); por isso a métrica principal do banco é o número de instruções, não os milissegundos locais.
- Não havia `DATABASE_URL` real nem Storage: nada foi medido contra produção.

## Linha de base (antes)

| Rota | Conexões | Instruções SQL | Observação |
|---|---|---|---|
| `/pessoas` (sem `limit`) | 0 | 0 | HTML estático, `no-store`, sem gzip (4,2 KB) |
| `/pessoas?limit=6`, `/api/people` | 1 (0 com cache) | 1 consulta + 3 do snapshot | cache de 30 s já existente |
| `/pessoas/{id}` e `/api/people/{id}` | 1 | 24 (12 consultas + 3 snapshots x 4) | 3 transações REPEATABLE READ sequenciais |
| `/pessoas/{id}?tab=activity` | 2 | 24 + votos | segunda conexão por requisição (não alterado) |
| `/panorama`, `/api/political-dashboard` | 1 | 2 a 3 (existência da tabela, catálogo, snapshot único) | cache de 300 s já existente; resposta com gzip, ETag, 304 |
| `/fontes-dos-dados` | 0 | 0 | `no-store`, sem gzip: 15 026 B por requisição; relê o JSON de evidências |
| `/assets/people-viewport.js` | 0 | 0 | `no-store`, relê o arquivo |
| CSS, SVG, `content.html`, diagramas | 0 | 0 | releitura de arquivo em cada requisição |

Renderização em CPU (ms, mediana, sem rede): `/` 0,1; `/como-funciona` 0,3; `/fontes-dos-dados` 0,3; `/panorama` (payload vazio) 1,2 a 1,5. O custo de CPU das páginas é desprezível frente ao banco. O parse dos JSON de orientação (`executive_orientation_evidence.json`, `senate_orientation_2026.json`, catálogos) já usava `functools.lru_cache(maxsize=1)`; não foi preciso mudar. A exceção é `data_sources/page.py`, que ainda relê o JSON executivo por requisição (ver "Fica para depois").

## Mudanças

| # | Mudança | Antes | Depois | Complexidade |
|---|---|---|---|---|
| 1 | `read_snapshot` reentrante (`database/public_profile.py`): chamadas aninhadas entram na transação aberta; as duas instruções `SET` vão em um único envio | 3 snapshots x (BEGIN, SET, SET, COMMIT) = 12 instruções de controle | 1 snapshot x (BEGIN, SET, COMMIT) = 3 | RTT por perfil O(1) em snapshots em vez de O(k) por bloco; consultas continuam O(q) |
| 2 | `fetch_person` envolve todas as leituras em um único snapshot | 24 instruções / 3 transações, três instantâneos distintos | 15 instruções / 1 transação; todos os fatos do perfil do mesmo instante | idem |
| 3 | `read_static_text` (`public_profile_web/static_text.py`): leitura de CSS, SVG, `content.html`, favicon e JS uma vez por versão do arquivo (chave: caminho, mtime_ns, tamanho) | 1 leitura de disco por requisição, O(tamanho) | 1 `stat` por requisição, O(1); relê sozinha se o arquivo mudar | O(1) por requisição |
| 4 | Memória positiva da existência da tabela anual do painel (`_dashboard_table_confirmed`) | 1 consulta `to_regclass` por miss de cache | 1 por processo após confirmar; ausência continua sendo reverificada | O(1) |
| 5 | Política de cache HTTP: `/fontes-dos-dados` com a mesma política das páginas estáticas; `people-viewport.js` com ETag e revalidação | 15 026 B `no-store`; JS sempre 629 B | 4 841 B com gzip (-68 %), 304 sem corpo; JS 304 | O(tamanho) uma vez por corpo (gzip em `lru_cache`) |

Números medidos depois: perfil da pessoa 24 para 15 instruções (-37 %), 3 para 1 transação. Em RTT de 20 ms isso é cerca de 480 ms para 300 ms de espera de banco por perfil (modelo, não medição de produção). `/fontes-dos-dados`: 15 026 B para 4 841 B. Leitura de arquivos estáticos: 7 rotas por 3 rodadas, zero leituras novas (antes uma por requisição). CPU local de CSS/HTML estático mudou de 0,017 para 0,011 ms: ganho real mas irrelevante em absoluto.

## Segurança dos caches

- Arquivos estáticos: a chave inclui mtime e tamanho; edição em desenvolvimento aparece na próxima requisição. `clear_static_text_cache()` está disponível aos testes.
- Existência da tabela: só o resultado positivo é guardado; tabelas não somem em operação normal. Dados do painel continuam no cache de 300 s já existente.
- Snapshot compartilhado só junta-se a uma transação já aberta; não troca nível de isolamento. Antes, o aninhamento falhava; agora é consistente.
- Nenhum dado de banco ganhou cache novo. A resposta dinâmica das pessoas continua `no-store`.

## Testes

`tests/test_request_optimizations.py`: leitura única e recarga por mudança de arquivo; sete rotas servidas sem releitura; snapshots aninhados abrem uma transação e um envio de `SET`; snapshots sequenciais continuam independentes; verificação da tabela memorizada só quando presente; política de cache; e (com `TEST_DATABASE_URL`) o perfil usa 1 conexão, 0 transações extras e no máximo 12 instruções, em SQL real.

## Fica para depois

- Atividade (`?tab=activity`) abre uma segunda conexão; compartilhar a conexão entre `fetch_person` e `fetch_votes` exige mudar a assinatura da aplicação. Em produção, a conexão (TLS e autenticação) é o maior custo individual restante; um pool por processo precisa de desenho próprio para o pooler do Supabase.
- `data_sources/page.py` relê e parseia o JSON executivo a cada requisição (0,3 ms). Um carregador compartilhado cacheado quebraria `tests/test_data_sources_page.py`, que substitui `Path.read_text`; não foi alterado para não interferir nos trabalhos paralelos.
- Compressão de respostas dinâmicas `no-store` (a Vercel comprime na borda; fazer no processo mudaria CPU sem ganho certo).
- `/pessoas` sem `limit` poderia ter ETag/gzip, mas compartilha o caminho com a página dinâmica.
- Renderização do painel com dados reais (milhares de linhas de histórico) não foi medida: não há dados reais locais. A linha do tempo é a maior parte do HTML (cerca de 65 % do tempo de renderização com payload vazio) e é linear em anos x séries.
- Teste de integração pré-existente que falha com banco (`test_release_checks_activity_with_real_sql...[200]`: espera 5 verificações e recebe 9 após a inclusão do painel) não foi tocado.

## Revisão posterior: histórico compartilhado entre anos e filtros

O portal agora usa um cache **versionado de histórico por território**, independente do ano selecionado e do modo de visualização. A mesma instrução SQL obtém as partições do ano e um fingerprint ordenado dos hashes das partições históricas. Se a versão já estiver no cache, o PostgreSQL não executa a reconstrução JSON do histórico e retorna esse campo como NULL; o adaptador reutiliza a cópia local. Se qualquer hash relevante mudar, a mesma SELECT devolve o histórico da nova versão e as partições correspondentes, sem misturar snapshots. Não foi criada ou aplicada tabela, migração ou carga em produção.

O cache histórico tem limite de 32 entradas e 8 MiB de bytes serializados. As entradas são imutáveis, devolvem cópias defensivas e usam trava por escopo para evitar reconstruções concorrentes do mesmo histórico. A consulta de versão continua O(N) nos hashes de N partições; o ganho é evitar a leitura/reconstrução/transmissão dos JSON históricos a cada troca de ano. A política já existente de cache completo da resposta, de 300 segundos, foi preservada: dentro dessa janela uma resposta pode permanecer na versão anterior; em cada miss a versão é conferida novamente. O fingerprint não é uma assinatura de integridade ou evidência oficial.

Na primeira leitura de cada versão, o adaptador reduz o histórico aos campos consumidos pela linha do tempo. Os detalhes anuais e fontes continuam nas partições do ano selecionado. Foram comparadas 612 células nacionais de arquivos e 676 células lidas com SQL real, nos dois modos de visualização: nenhuma diferença semântica.

Medição com 338 partições nacionais públicas copiadas para uma transação de rollback em PostgreSQL local descartável:

- Resultado antigo do banco para 2025: 534.232 bytes, sendo 485.408 do histórico.
- Primeira leitura versionada: 534.287 bytes do banco; a redução local deixa 278.818 bytes de histórico retornado à aplicação.
- Leitura seguinte de 2025 com a versão já carregada: 48.883 bytes do banco, sem retransmitir histórico; uma SELECT por leitura.
- Alternar para 2024 ou 2026 também reutiliza a mesma versão. EXPLAIN ANALYZE confirmou que a subconsulta e os expansores JSON históricos não foram executados na leitura quente.
- Tempos locais de uma amostra: 65,6 ms na primeira leitura e 4,8 ms na leitura quente de 2025. Não são medianas nem medição de produção e não incluem latência externa.

O formato de publicação zlib em `history.py` permanece disponível, mas a otimização ativa acima **não depende de uma nova tabela compactada**. O decoder passou a recusar base64 inválido, bytes extras após zlib, schema incompatível e formato incorreto de linhas.

Validação posterior completa: **2.512 testes aprovados**, incluindo integração em banco exclusivamente descartável. A expectativa antiga de cinco verificações do release foi substituída pela verificação dos caminhos e estados exigidos, preservando também as quatro verificações do panorama.
