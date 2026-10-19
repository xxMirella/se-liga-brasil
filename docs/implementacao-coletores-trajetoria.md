# Desenvolvimento dos coletores de trajetória pública

Trabalho iniciado em 17/10/2026 a partir dos seis itens de [fontes e coletores faltantes](auditoria-cobertura-trajetoria-publica.md). Esta página distingue código entregue, integração e cobertura efetiva. Criar um coletor não significa que os fatos já estejam ingeridos ou que todo o histórico esteja coberto.

## Divisão de responsabilidades

1. Câmara dos Deputados: detalhes, autores, tramitações, resultados, votações e referências oficiais a normas, conforme os contratos disponíveis.
2. Câmara Municipal de São Paulo: projetos e deliberações SPLEGIS; identidade pessoal revisada e limites dos registros municipais.
3. ALESP, ALERJ e Senado: capacidades legislativas por instituição, com domínios não suportados declarados antes de acessar a rede.
4. Histórico eleitoral e mandatos: planejamento por eleição/UF/período, reaproveitamento de arquivos e evidências institucionais de exercício.
5. Empresas: arquivos oficiais CNPJ, empresas/estabelecimentos/sócios e identificação conservadora dos vínculos pessoais.
6. Parcerias e execução de recursos: instrumentos oficiais, emendas e papéis comprovados, sem inferir parceria de simples coincidência nominal.

Cada frente possui seus módulos, testes e documento. Alterações de contratos compartilhados, migrações e integração do orquestrador são coordenadas na revisão final para evitar implementações concorrentes incompatíveis.

## Contratos de desenvolvimento

- Aquisição usa os mecanismos existentes de HTTP oficial, cache, download limitado, ritmo por host e arquivos originais imutáveis.
- Normalização não acessa banco nem rede. Projeção recebe dados validados e preserva fonte, período, qualidade e identidade interna.
- Identificadores de documentos e instrumentos são chaves técnicas desses fatos. Identificadores pessoais externos não substituem `person_id` nem autorizam vínculo por homonímia.
- Autoria, relatoria, resultado coletivo, voto individual, lei publicada, mandato e exercício permanecem conceitos distintos.
- O coletor retorna somente o que seu contrato comprova; resultados vazios, falhas, limites de páginas e domínios não suportados têm tratamentos diferentes.
- As pendências continuam na fila existente. Recursos compartilhados são planejados por fonte e partição, evitando baixar a mesma votação, eleição ou arquivo empresarial para cada pessoa.
- Funções têm responsabilidade explícita, até 60 linhas, aninhamento até três e complexidade cognitiva estrutural até 15. Helpers representam conceitos reutilizáveis; não apenas escondem laços ou ramificações.
- Leitura de n registros custa O(n); índices em memória permitem consulta média O(1) por chave, com memória limitada pelo lote/escopo. Índice B-tree de banco não é O(1).

## Verificação

Cada frente testa contratos, limites, ambiguidade e reutilização de recursos conforme seu comportamento. A integração executa Ruff, revisão estrutural e regressão. Testes SQL usam schema isolado e rollback; exemplos fictícios nunca são inseridos nas tabelas de produção.

Verificação final desta entrega: 200 testes locais passaram; cinco testes SQL dirigidos passaram, incluindo migração/reaplicação, tramitações Câmara, rejeições/revisão CMSP e vínculos empresariais. Ruff, formatação e revisão estrutural sem achados. A execução integral com todos os testes remotos foi interrompida por sinal 143, sem resultado final; não é reportada como aprovada. A bateria SQL dirigida foi concluída separadamente com rollback obrigatório. Links locais e IDs das duas páginas da prévia foram conferidos; filtros de cargo/ano e agrupamento mensal foram verificados no navegador.

Até haver execução comprovada, nenhum coletor novo deve aparecer como fonte com cobertura completa. A consulta pública permanece separada da aquisição: abrir um perfil não dispara downloads.

## Núcleos entregues e integração restante

- [Câmara](camara-historico-legislativo.md): extensão opt-in de aquisição e projeção de tramitações/autorias verificadas; votos nominais e normas ainda exigem projeção e contratos completos.
- [CMSP](crawler-cmsp.md): coleta anual, validação e projeção de projetos/autores revisados; observações sem data não viram votação ou lei.
- [ALESP/Senado/ALERJ](cobertura-legislativa-instituicoes.md): aquisição de tramitações ALESP e processos/votações Senado; ALERJ legislativa não suportada. Novos dados ainda precisam de projeções tabulares e despacho.
- [Cobertura histórica](historico-eleitoral-e-mandatos.md): avaliação read-only e planejamento de recursos compartilhados. Recibos persistentes e integração de execução continuam pendentes. A completude básica passou a tratar mera presença de autoria como parcial.
- [CNPJ](crawler-receita-federal.md): streaming, seleção em lote, staging e SQL de empresas/estabelecimentos/vínculos revisados. Migração 0016 registrada no comando de migração, sem aplicação em produção nesta entrega; catálogo, despacho e coleta real continuam pendentes.
- [Transferegov](crawler-transferegov.md): aquisição paginada e normalização com duas amostras oficiais mínimas; persistência tabular e encadeamento financeiro completo ainda não entregues.
- [Votações e armazenamento analítico](votacoes-senado-e-arquitetura-analitica.md): fontes nominais verificadas e recomendação PostgreSQL + Parquet/DuckDB. O repositório analítico ainda é desenho, não pipeline instalado.

A [aba de atuação](prototipo-linha-do-tempo/atuacao.html) é uma prévia funcional de filtros e apresentação com fatos fictícios. Não é um frontend conectado aos novos coletores. Todos os seis itens receberam agentes próprios; uma sétima frente verificou fontes nominais e arquitetura analítica.

## Acompanhamento por entregáveis no Trello

Os cartões representam resultados verificáveis, não agentes. Implementação de núcleo, integração e coleta em produção são etapas diferentes nos critérios de aceite. O backend público ainda está no backlog; não é apresentado como funcional.

- [Remuneração ALESP vinculada às pessoas da base](https://trello.com/c/WbTIPOD6)

- [Histórico legislativo da Câmara em tabelas](https://trello.com/c/OauV6on1/2-hist%C3%B3rico-legislativo-da-c%C3%A2mara-em-tabelas)
- [Projetos e autorias municipais de São Paulo em tabelas](https://trello.com/c/JYgqB6ML/3-projetos-e-autorias-municipais-de-s%C3%A3o-paulo-em-tabelas)
- [Tramitações ALESP e processos legislativos Senado](https://trello.com/c/BtXIvfzB/4-tramita%C3%A7%C3%B5es-alesp-e-processos-legislativos-senado)
- [Cobertura histórica por pessoa, cargo e período](https://trello.com/c/kQlyhdTd/5-cobertura-hist%C3%B3rica-por-pessoa-cargo-e-per%C3%ADodo)
- [Vínculos empresariais comprovados com dados CNPJ](https://trello.com/c/vHhPI7Vq/6-v%C3%ADnculos-empresariais-comprovados-com-dados-cnpj)
- [Instrumentos de parceria e execução de recursos](https://trello.com/c/vAUYyBpg/7-instrumentos-de-parceria-e-execu%C3%A7%C3%A3o-de-recursos)
- [Dataset de votações nominais do Senado](https://trello.com/c/UkJA7zSD/8-dataset-de-vota%C3%A7%C3%B5es-nominais-do-senado)
- [Repositório analítico gratuito e datasets da trajetória](https://trello.com/c/Vuz4ZtNi/9-reposit%C3%B3rio-anal%C3%ADtico-gratuito-e-datasets-da-trajet%C3%B3ria)
- [Prévia pública: feitos e atribuições por cargo](https://trello.com/c/nvAICRBJ/10-pr%C3%A9via-p%C3%BAblica-feitos-e-atribui%C3%A7%C3%B5es-por-cargo)
- [API pública de perfil e atuação com dados reais](https://trello.com/c/QYPdT5Fv/11-api-p%C3%BAblica-de-perfil-e-atua%C3%A7%C3%A3o-com-dados-reais)
- [Validação numérica TSE e reprocessamento idempotente](https://trello.com/c/cL8TJmYB/12-valida%C3%A7%C3%A3o-num%C3%A9rica-tse-e-reprocessamento-idempotente)
- [Fonte legislativa ALERJ validada e coletor operacional](https://trello.com/c/HhIf3IMo/13-fonte-legislativa-alerj-validada-e-coletor-operacional)
