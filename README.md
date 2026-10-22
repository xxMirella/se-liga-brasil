# Se Liga, Brasil

Serviços Python para coletar, validar e ingerir dados oficiais de transparência política, com histórico e proveniência. PostgreSQL 17+; código Python 3.12+.

## Estrutura

Cada pasta em `src/` representa um módulo reutilizável ou um serviço:

- `normalization/`: biblioteca de normalização de textos, datas, identificadores, valores e booleanos.
- `service/data_validation/`: contratos de identidade e verificação genérica de existência/mudanças.
- `storage/`: persistência local privada, escrita atômica, hashes e índices em disco.
- `database/`: conexão PostgreSQL, verificação de schema e adaptador de consultas de existência.
- `service/ingestion/`: reconciliação em lotes, versões, transações e auditoria. Recebe uma estratégia de projeção por conector.
- `service/crawling/`: orquestração das fases do crawler.
- `crawlers/tse/`: descoberta no catálogo TSE, download, interpretação do formato eleitoral e projeções específicas.
- `code_quality/`: revisão estrutural de carga cognitiva e fronteiras de módulos.
- `application/`: composição dos serviços e comandos de linha de comando.

O nome de distribuição `se-liga-brasil` identifica o pacote instalado; não há um pacote com esse nome dentro de `src/`.

## Instalação

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install -e . --no-build-isolation
```

O projeto é executado a partir deste checkout. SQLs e configurações estão em `db/` e `config/`; não publicar apenas um wheel sem esses recursos. As credenciais são carregadas externamente por `--env-file` ou pelas variáveis `DATABASE_URL`/`SUPABASE_URL` contendo uma conexão PostgreSQL. Não copiar credenciais para o repositório.

## Crawler modular

Para executar todas as etapas para os 26 estados e o Distrito Federal em 2026,
rode este único comando na pasta do projeto:

```sh
.venv/bin/se-liga-brasil run --years 2026 --ufs all --env-file /home/mirella/projetos/mdqc-knowledge-center/.env
```

`--ufs all` força o recorte nacional mesmo se a configuração tiver uma UF específica.
O comando coleta apenas arquivos publicados pelo TSE. Para descobrir todos os anos do catálogo,
substitua `--years 2026` por `--years all`.

Após descobrir os recursos, o terminal mantém um único painel atualizado no mesmo lugar,
sem imprimir uma linha por arquivo. Mostra etapa, recurso atual, total de arquivos,
porcentagem do download atual, MiB recebidos, arquivos concluídos,
quantos ainda faltam processar, cache e arquivos com rejeições/falhas. Sem tamanho informado pelo servidor, mostra
os bytes recebidos sem estimar uma porcentagem. Arquivos reaproveitados do cache também
avançam o contador; falhas ficam contadas separadamente. Ao redirecionar a saída,
os eventos JSON preservam os contadores, sem caracteres de animação.

Cada execução cria `data/tse/logs/<id-da-execução>/rejections.ndjson` com todos os
motivos de rejeição e falha, identificando etapa, recurso, código, explicação, arquivo
interno e linha quando disponíveis. `events.ndjson` registra os demais eventos.
O painel mostra os três avisos mais recentes e o caminho do log; o relatório completo
permanece no arquivo. O contador considera recursos distintos: vários registros rejeitados
no mesmo ZIP contam como um arquivo com rejeições. Rejeições de validação e de ingestão
ficam identificadas pela etapa, inclusive quando o mesmo registro aparece nas duas.
Arquivos com registros em quarentena podem ter os demais registros válidos ingeridos.

O crawler mantém manifests por recurso com caminho, hash SHA-256 e data da verificação.
Antes de baixar, verifica se o arquivo existe e se o hash confere. Arquivos íntegros
verificados nas últimas 24 horas são reaproveitados sem nova requisição de download;
arquivos ausentes ou corrompidos são baixados novamente. Ao vencer esse prazo, consulta
o TSE novamente para detectar alterações. O prazo é configurável por
`force_recheck_after_hours`; respostas HTTP 304 reaproveitam o arquivo local.
Assim, reiniciar o mesmo comando retoma o conjunto de arquivos sem baixar tudo novamente.

Falhas são emitidas no terminal com etapa (`download`, `validate` ou `ingest`), nome e
URL do recurso, ano, UF, código, mensagem e arquivo/função/linha do código. Erros globais
informam o comando e a localização. Erros saem em stderr; o resumo final fica em stdout.
O crawler continua os outros arquivos quando um recurso falha e retorna código 1 se houver
falhas ou rejeições. O resumo da execução fica em `data/tse/last-run.json` quando a
execução alcança a etapa de ingestão. Limites de tamanho são respeitados: excedê-los gera
erro explícito, não uma declaração de cobertura nacional completa.

Comandos separados para inspecionar cada etapa:

Para candidaturas de senador, deputado federal e deputado estadual de São Paulo,
incluindo 2018, 2022 e 2026:

```sh
.venv/bin/se-liga-brasil run --years 2026,2022,2018 --ufs SP --office-codes 5,6,7 --kinds candidate,history,asset --env-file /home/mirella/projetos/mdqc-knowledge-center/.env
```

O recorte por cargo tem identidade de staging própria e os bens acompanham apenas
as candidaturas selecionadas. O histórico preserva outros cargos anteriores dessas
pessoas. Esses dados descrevem candidaturas e resultados, não uma lista oficial de
parlamentares em exercício. Para conferir os atuais, usar também Câmara, Senado e Alesp.

Depois do download, o painel mostra validação e ingestão por lote, além do tempo
transcorrido e do tempo desde o último avanço. Atualiza os perfis após cada arquivo
de candidaturas/histórico, com limite de 120 segundos por atualização e 10 segundos
de espera por lock. Ingestão continua finita: mostra `Finalizado` ao terminar e sai;
`Ctrl+C` encerra com status de interrupção e código 130. Não há loop de monitoramento.

```sh
.venv/bin/se-liga-brasil discover --years 2026 --ufs PA
.venv/bin/se-liga-brasil download --years 2026 --ufs PA --kinds candidate,history,complement,asset
.venv/bin/se-liga-brasil validate --years 2026 --ufs PA --kinds candidate,history,complement,asset
.venv/bin/se-liga-brasil db-migrate --env-file /caminho/seguro/.env
.venv/bin/se-liga-brasil ingest --years 2026 --ufs PA --env-file /caminho/seguro/.env
```

`run` executa descoberta, download, validação e ingestão. `--years all` descobre conjuntos históricos no catálogo. A configuração padrão cobre 2026 e todas as UFs, incluindo bens, histórico, dados complementares, propostas de governo e certidões. Arquivos de documentos são grandes; configure limites e execute por UF quando necessário. As fases usam planos locais, e a fase `ingest` exige o mesmo recorte por UF da validação.

Downloads, arquivos tratados e quarentena ficam em `data/tse/`, excluída do Git. Somente dados validados chegam às projeções. Um arquivo idêntico já concluído é ignorado; conteúdo alterado gera uma versão preservando a anterior. Falhas e rejeições retornam saída não zero. Não há agendamento automático instalado: o comando `run` pode ser chamado por um agendador de infraestrutura.

O TSE fornece dados eleitorais. Salários e exercício/saída efetiva do cargo precisam de conectores das casas legislativas. Proposta de governo não é projeto de lei; uma certidão é armazenada como documento, sem interpretação automática de condenação.

## Qualidade e testes

```sh
.venv/bin/ruff check src tests .codex/hooks
.venv/bin/ruff format --check src tests .codex/hooks
.venv/bin/pytest -q
.venv/bin/se-liga-brasil review
```

Testes locais não conectam ao banco. Testes marcados como `integration` exigem `TEST_DATABASE_URL` ou `SE_LIGA_BRASIL_TEST_ENV_FILE` explicitamente. Criam um schema exclusivo dentro de uma transação com rollback obrigatório; dados fictícios e o próprio schema são revertidos.

O hook do projeto fica em `.codex/hooks.json`, cobre edições e comandos de shell, mede carga cognitiva e solicita revisão semântica de system design. O evento `Stop` pede correção de achados pendentes. Ver [revisão e arquitetura](docs/crawler-e-ingestao.md) para limites e ativação no Codex.

## Documentação

- [Fontes oficiais nacionais e das 27 UFs](docs/fontes-oficiais-perfis-parlamentares.md)
- [Modelo relacional](docs/modelo-de-dados.md)
- [Crawler, reconciliação genérica e decisões de arquitetura](docs/crawler-e-ingestao.md)
- [Convenções obrigatórias](AGENTS.md)
- [Identidade, filiação e contexto temporal](docs/identidade-filiacao-e-contexto.md)

## ALESP

Crawler modular de remuneração mensal: [execução e modelo](docs/crawler-alesp.md).
Inventário de fontes: [dados oficiais ALESP](docs/fontes-alesp.md).
Correção de valores patrimoniais negativos TSE: [política numérica](docs/tse-numeric-validation.md).

Identidade por dados pessoais e verificações: [identidade-pessoal.md](docs/identidade-pessoal.md).
Fontes oficiais de aposentadorias e pensões: [fontes-previdenciarias.md](docs/fontes-previdenciarias.md).

Serviço de diagnóstico e coleta de lacunas: [completude-e-enriquecimento.md](docs/completude-e-enriquecimento.md).


Cargo público atual e flag na pessoa: [modelo e regras](docs/pessoa-cargo-atual.md). Pesquisa de conexões oficiais entre identidade, vínculos e pagamentos: [portais de transparência](docs/portais-conexao-dados.md).

Funcionamento exato, campos e tabelas preenchidas por crawler: [guia dos crawlers](docs/crawlers-funcionamento.md).

Consulta salarial genérica diretamente nas tabelas: [person_payments.sql](db/queries/person_payments.sql).

Consulta pública de pessoas: [desenho do backend e frontend](docs/backend-frontend-linha-do-tempo.md) e [protótipo visual com dados fictícios](docs/prototipo-linha-do-tempo/index.html).

Diagnóstico das pendências: [erros e bloqueios encontrados](docs/erros-e-bloqueios-pendencias.md).

Cobertura de propostas, resultados legislativos e trajetória histórica: [auditoria e serviço proposto](docs/auditoria-cobertura-trajetoria-publica.md).

Desenvolvimento por entregáveis, limites de integração e cartões Trello: [coletores da trajetória](docs/implementacao-coletores-trajetoria.md).

Votos nominais e análise gratuita dos arquivos: [fontes e arquitetura analítica](docs/votacoes-senado-e-arquitetura-analitica.md).

Gastos com equipe de gabinete: [coleta, cálculo por cargo e histórico público](docs/gastos-equipe-gabinete.md).

Fonte de salário individual do Senado: [API nominal oficial e regras de associação](docs/fonte-api-remuneracao-senado.md).
