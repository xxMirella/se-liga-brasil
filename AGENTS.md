# Convenções do Se Liga Brasil

## Nomenclatura explícita

- Nomes de tabelas, colunas, índices, funções, variáveis e APIs devem explicar o conceito e fazer sentido no domínio deste projeto.
- Use inglês consistente no código e `snake_case` no PostgreSQL; não misture idiomas nos identificadores.
- Evite palavras genéricas, abreviações obscuras e nomes com sentidos ambíguos quando houver uma alternativa precisa.
- Use `political_party` e `political_party_affiliation`, nunca `party` para partido político. Use `political_party_id` para a chave correspondente.
- Diferencie autoria, relatoria, voto individual, resultado coletivo, mandato e exercício efetivo também nos nomes.
- Ao renomear, atualize referências, constraints, índices, projeções, testes e documentação. Bancos existentes devem receber uma migração que preserve dados.

## Python e revisão obrigatória

- Todo código executável deste projeto deve ser Python 3.12+; não criar arquivos JavaScript/TypeScript, manifests Node ou `node_modules`.
- Cada função deve ter uma responsabilidade, nomes explícitos e uma leitura simples. Validação do domínio não acessa rede ou banco.
- Executar a revisão de system design após alterações e antes de concluir. Corrigir os achados estruturais e revisar também a semântica, que o hook não consegue provar.
- Limites iniciais por função: 60 linhas, complexidade cognitiva estrutural até 15 e profundidade de controle até 3. Extrair responsabilidades quando exceder; não esconder complexidade em funções genéricas.
- Distinguir carga cognitiva de complexidade algorítmica. A varredura de n registros exige O(n); priorizar streaming, índices e lotes. Evitar N+1 remoto, varreduras repetidas e O(n²) sem necessidade.
- Dados só chegam às projeções após normalização, validação e identificação de fonte/data. Mudanças mantêm histórico; ausência em um arquivo não prova saída do cargo.
- O hook do projeto está em `.codex/hooks.json`; não depender de caminhos globais de outras ferramentas. Testes não devem deixar dados fictícios no banco de produção.

## Arquitetura modular de src

- Não criar pacote agregador com o nome do projeto em `src/`. Cada pasta representa um módulo, serviço ou biblioteca com responsabilidade explícita.
- Normalizadores escalares pertencem a `normalization`; regras e chaves específicas de uma fonte pertencem ao seu crawler.
- Existência e comparação de dados pertencem a `service/data_validation`, com identidade fonte + tipo + chave. Adaptadores PostgreSQL ficam em `database`.
- Ingestão genérica recebe a descrição da fonte e uma estratégia de projeção; não deve importar regras do TSE.
- Use a API em lotes na varredura. A função pontual de existência não deve gerar N+1 remoto.

- Todos os crawlers devem ficar em `src/crawlers/<fonte>/`; o crawler do TSE fica em `src/crawlers/tse/`. Não criar crawlers no topo de `src/`.

- Todos os serviços da aplicação devem ficar em `src/service/<serviço>/`. A verificação genérica de existência fica em `src/service/data_validation/`; a ingestão fica em `src/service/ingestion/`; a orquestração dos crawlers fica em `src/service/crawling/`. Bibliotecas e adaptadores continuam separados.
- Regra de localização: tudo o que for tratado como serviço pertence a `src/service/`, sem exceções implícitas. Ao criar um componente, definir sua responsabilidade e se ele é serviço, biblioteca reutilizável ou adaptador; serviços não ficam na raiz de `src/` nem dentro dos conectores.
