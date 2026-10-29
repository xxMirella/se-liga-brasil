# Painel: histórico pré-calculado por território

Documento técnico de engenharia (28/10/2026). Não contém credenciais.

## Problema

A linha do tempo do painel depende só do território, mas era remontada, a cada consulta nova, a partir de todas as partições anuais (361 a 713 linhas) e retransmitida inteira (cerca de 0,5 MB para o Brasil). O cache guardava a resposta por (ano, território, visão), então trocar de ano refazia tudo. Cada requisição abria uma conexão nova com o banco.

## O que mudou

1. **Tabela `se_liga_brasil.political_dashboard_history`** (`db/political_dashboard_history.sql`): uma linha por território, com RLS ativada e `REVOKE ALL` para `anon` e `authenticated`, como a tabela anual. O payload é o JSON canônico `political_dashboard_history.v1` comprimido com zlib (`payload_zlib`), mais `content_sha256`, `row_count`, `uncompressed_bytes` e `published_at`.
2. **Publicação**: `AnnualDashboardRepository.activate_partitions` reconstrói, na mesma transação, o histórico dos territórios tocados (todos os publicadores passam por ele). Sem a tabela (antes da migração) a etapa não faz nada. A republicação de dados idênticos não altera a linha (compara o digest). A remoção do Distrito Federal inválido também atualiza o histórico do DF.
3. **Leitura**: uma única instrução SQL traz as partições do ano e, para cada território, o digest do histórico. O texto do histórico só viaja quando o digest difere da cópia que o processo já tem (`VersionedHistoryCache`, por território, validada no banco a cada requisição). Trocar de ano, visão ou estado vizinho não retransmite nem reconstrói o histórico.
4. **Fallback**: se a tabela não existe ou falta a linha de algum território, a leitura usa as linhas anuais (com a mesma redução, aplicada em Python). Por isso a ordem de deploy (código antes ou depois da migração) não causa erro, e o rollback é seguro.
5. **Conexão de leitura pública** (`database/public_read_connections.py`): até 2 conexões ociosas reaproveitadas por processo, descartadas se velhas (60 s), quebradas ou dentro de transação; se uma conexão reaproveitada morreu, a operação é repetida uma vez em conexão nova. Para hosts `*.pooler.supabase.com` a leitura usa a porta 6543 (modo transação); os crawlers continuam em modo sessão (`session_connection_string`, porta 5432). Hoje só o painel usa o pool.
6. **Versão do dataset**: `dataset_version` (SHA-256 truncado dos digests do histórico e das partições do ano) entra no cálculo do ETag (`prepare_public_response`) e aparece no JSON da API (`dataset_version`, `dataset_generated_at`). O HTML não mostra esses campos.

## Fase 2: o que o histórico guarda

Campos lidos pelo desenho (verificados em `timeline.py`, `orientation_timeline.py`, `presidential_explanations.py`, `executive_orientation_presentation.py`, `senate_orientation_2026.py`, `orientation_composition.py`):

- Legislativo (Senado, Câmara, assembleias, câmaras municipais): `political_parties`, `total`, `coverage`, `snapshot_on`, `institutional_status` (mais ano, instituição, território e `office_kinds`). Descartados: membros/segmentos, `current`, fontes, `aggregation_basis` etc.
- Executivo (governos estaduais, prefeituras): só partido e situação do partido de cada registro e de cada período (`political_party`, `political_party_status`). Sem nomes, datas ou URLs.
- Presidência: anos que a página explica (mais de uma pessoa, interinidade, mandato curto, mudança de partido, evento revisado ou contexto) mantêm nomes, datas, capacidade de exercício e fontes. Os demais anos guardam só identidade (`person_id`, `exercise_id`, datas) e partido, que a classificação de orientação usa. O critério é o próprio `presidential_year_explanation`, para não divergir da página.

Desvio do pedido: a **categoria de orientação não é gravada**. Ela continua derivada, na renderização, dos grupos de partido, porque o modelo de classificação está sendo alterado por outros trabalhos; gravar a categoria congelaria uma versão antiga do modelo. O HTML é idêntico (abaixo).

O detalhe (segmentos, períodos de partido, fontes) permanece na partição `(ano, território, instituição)`.

## Medições

Banco real, somente leitura, a partir desta máquina (RTT de um `SELECT 1`: 0,14 s). Mediana de 3 execuções frias (aplicação nova, cache vazio, conexão nova, renderização incluída).

### Antes

| Caso | Tempo frio | Queries | Histórico (JSON) |
|---|---|---|---|
| BR 1992 | 2,31 s | 2 | 521.963 B |
| BR 2000 | 2,35 s | 2 | 521.963 B |
| BR 2026 | 2,54 s | 2 | 521.963 B |
| SP 2000 | 2,14 s | 3 | 445.107 B |
| SP 2026 | 2,16 s | 3 | 445.107 B |

Componentes medidos: conexão nova 0,87 s; instrução do snapshot do Brasil 0,62 s, devolvendo 662.770 B.

### Depois

O banco real ainda não tem a tabela (nada foi aplicado). Os números de rede abaixo vêm de instruções equivalentes executadas só para leitura no banco real; o restante vem de uma cópia local descartável dos mesmos dados.

| Medida | Antes | Depois |
|---|---|---|
| Histórico do Brasil por consulta nova com cache frio (bytes do banco ao servidor) | 521.963 | 11.920 comprimidos (cerca de 15,9 KB em base64) |
| Idem, trocando só o ano (cache quente) | 521.963 | 0 |
| Histórico de SP (cache frio) | 445.107 | 3.770 comprimidos |
| Instrução do snapshot BR no banco real | 0,62 s | 0,143 s (só partições) a 0,149 s (partições + 16 KB de histórico, simulado) |
| Conexão por requisição | 0,87 s | 0 em instância quente |
| Queries, BR, instância quente, trocando o ano | 2 | 1 |
| Queries, SP, instância quente | 3 | 2 (catálogo + snapshot) |
| Queries, instância fria | 2 (BR) / 3 (SP) | 2 (BR) / 3 (SP) |

Estimativa para uma consulta nova em instância quente: 0,14 a 0,15 s de banco mais a renderização, contra 2,1 a 2,5 s. Em instância fria sobram a conexão (0,87 s), a verificação da tabela (0,14 s) e a instrução (0,15 s). É uma composição de componentes medidos, não uma medição fim a fim em produção, que só será possível depois do `--apply`.

Tamanho total da tabela na simulação: 32 territórios, 5.962 linhas anuais lidas, 2.184.204 B de JSON, 73.687 B comprimidos. O histórico em memória, já expandido na página, continua com cerca de 310 KB para o Brasil (era 522 KB); esse valor não trafega pela rede.

## Equivalência do HTML

- Os 7 casos medidos (BR 1992, 2000, 2026; BR 2026 e SP 1992 em orientação política; SP 2000 e 2026) foram gerados antes (banco real, código antigo) e depois (cópia local dos mesmos dados, código novo): os arquivos HTML são idênticos byte a byte.
- Varredura ampliada: 1.104 páginas completas (Brasil, todos os anos de 1826 a 2026; 27 estados em 13 anos de referência; duas visões) comparadas entre o caminho antigo e o novo na mesma cópia local, sem nenhuma diferença.
- Testes automatizados com banco descartável cobrem versão, invalidação, concorrência, fallback e a equivalência das células da linha do tempo e das explicações presidenciais.

Conteúdo da API: o campo `history` do JSON de `/api/political-dashboard` perde os campos que a página não usa (por exemplo, nomes de governadores e fontes em anos comuns) e ganha `dataset_version` e `dataset_generated_at`. Nenhum consumidor interno depende disso, mas é uma mudança de contrato da API pública.

## Operação

- Preencher (dry-run por padrão, só leitura; `--apply` cria a tabela e grava, em uma transação com lock consultivo): `scripts/build_political_dashboard_history.py [--territory UF ...] [--apply]`.
- Publicações anuais (`scripts/build_political_dashboard_annual.py --apply`, que mantém `--activate` como sinônimo; sem a flag nada é gravado no banco) passam a atualizar o histórico dos territórios tocados.
- Reverter: `scripts/rollback_political_dashboard_history.py [--apply]` (executa `db/rollbacks/political_dashboard_history_rollback.sql`). A aplicação volta ao cálculo a partir das linhas anuais, que não são tocadas.
- Dry-run no banco real (28/10/2026): a tabela não existe; seriam criados a tabela e 32 linhas novas, lendo 5.962 linhas anuais, 73.687 B comprimidos no total, em cerca de 11 s.

## Riscos e limites

- Se os eventos presidenciais revisados (`presidential_transition_catalog`) ou os critérios de `presidential_year_explanation` mudarem, é preciso reconstruir o histórico (`--apply` do script) para os anos afetados mostrarem o detalhe.
- Linhas anuais gravadas fora de `activate_partitions` não atualizam o histórico; o digest só muda na próxima publicação ou reconstrução manual. A versão no ETag reflete o que está na tabela de histórico.
- A porta 6543 (modo transação) é usada nas leituras públicas de hosts do pooler; as leituras não dependem de estado de sessão, mas vale confirmar no ambiente de produção.
- Só o painel usa o pool; as demais rotas públicas continuam abrindo uma conexão por requisição.
- O cache de respostas por consulta (300 s, 4 MB) ainda guarda o histórico expandido dentro de cada resposta; o cache por território evita a retransmissão, não essa duplicação em memória.

## Aplicação no banco real (29/10/2026)

- Migração e publicação aplicadas com `scripts/build_political_dashboard_history.py --apply`:
  tabela `se_liga_brasil.political_dashboard_history`, 32 linhas, 176 kB no total
  (73.687 B de payload comprimido). Segunda execução: 32 linhas `unchanged` (idempotente).
- Medição ponta a ponta no servidor local (banco real), antes → depois:
  `/panorama` primeira chamada 3,82 s → 1,79 s (inclui conexão fria); `/panorama?year=2020`
  0,75 s → 0,30 s; `/panorama?year=2010` (ano novo) 0,17 s; repetição em cache ≈ 0,013 s.
- HTML de `/panorama` e `/panorama?year=2020` byte a byte igual ao de antes da migração.
- `/api/political-dashboard` devolve `dataset_version`; ele compõe o ETag das respostas.
- Servidor reiniciado sem erros no log. A leitura pública usa o pool de leitura; com URL do
  pooler em 6543 o código já aplica o modo transação (`public_read_connections.py`). Em
  serverless cada instância fria paga uma conexão nova, mas não remonta o histórico.
- Reverter: `scripts/rollback_political_dashboard_history.py` (ou `db/rollbacks/`). Sem a
  tabela o leitor volta ao cálculo antigo.
