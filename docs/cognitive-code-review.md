# Revisão cognitiva incremental

A skill `cognitive-code-review` está instalada em `/home/mirella/.codex/skills/cognitive-code-review/SKILL.md`. Pode ser solicitada como `$cognitive-code-review`. Orienta revisão após cada lote significativo de alterações; não é um monitor de teclas nem comprova Big O automaticamente.

O projeto possui um hook configurado em `.codex/hooks.json` para revisão estrutural após ferramentas e ao concluir. Os limites são 60 linhas por função, pontuação cognitiva estrutural 15 e profundidade 3. A análise semântica de responsabilidade, N+1 e complexidade permanece tarefa do agente. A presença da configuração não comprova que a sessão carregou os hooks.

## Coleta de identidades revisadas

`collect_reviewed_identities` separa planejamento dos recursos, aquisição e montagem/validação. O planejamento usa um dicionário por URL e elimina downloads duplicados entre casos e referências. A montagem preserva a origem do perfil e elimina referências repetidas dentro de cada caso. O orçamento de download continua compartilhado.

Se C é o número de casos, R o total de referências e U o número de URLs únicas, o custo de planejamento/montagem é O(C + R), com O(1) médio por consulta ao índice; a aquisição ocorre U vezes. Leitura, parsing, hashing e transferência dependem dos bytes envolvidos. O algoritmo anterior também era O(C + R), mas podia solicitar a mesma URL repetidamente. Não houve transformação de O(n²) em O(1).

A materialização dos resultados de aquisição usa memória proporcional aos bytes únicos adquiridos, limitada pelo orçamento do crawler. Para catálogos muito maiores, considerar armazenar apenas referências e processar perfis em lotes, preservando a deduplicação.

Validação: `tests/test_alesp_reviewed_resources.py` verifica duas identidades com referências compartilhadas e repetidas: apenas duas aquisições para duas URLs únicas, mantendo a rastreabilidade de cada identidade.
