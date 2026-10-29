# Página `/comparacao-de-classificacoes`

Compara, por partido político e período, duas formas de classificação:

- **A. Pesquisa de especialistas** (catálogo atual, `political_orientation_catalog.json`): percepção de
  especialistas em escala 0–10, só para 2018 e 2022. Não é a opinião da população nem autodeclaração.
- **B. Modelo de atuação** (`party_orientation_model`): votos, políticas e iniciativas, escala −1..+1
  (equivale a `5 + 5 × nota` na escala 0–10).

Resultados: concorda, discorda, concorda em parte, não comparável. Centro-esquerda conta como esquerda
e centro-direita como direita. Lacunas ficam como "evidência insuficiente"; nada é preenchido.
Rótulos "extrema" aparecem como "proposta, aguarda revisão humana".

**Autodeclaração (coluna C):** fora desta versão. Os textos arquivados em `discourse/` ainda não têm
leitura revisada (`rubric_pending`). Incluir só com registro revisado, por partido e período.

## Como regenerar

Produção não tem `data/`; a página lê só `src/service/party_orientation_comparison/snapshot.json`.

```
.venv/bin/python scripts/build_party_orientation_comparison_snapshot.py          # simulação
.venv/bin/python scripts/build_party_orientation_comparison_snapshot.py --apply  # grava o JSON
```

Rode depois de cada execução de `classify-political-parties`, revise o diff e reinicie o servidor.
Se as saídas misturarem versões de modelo ou de rubrica (regeneração em curso), o script recusa.

## Limites

Pesquisa só em 2018/2022; votos de 2003–2014 misturam ideologia com governo × oposição; poucas
votações temáticas por legislatura (menos de três = nota indicativa).
