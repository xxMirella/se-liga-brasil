# Modelo de classificação partidária por atuação

Versão do modelo: `party_orientation_model.v1`. Biblioteca pura em `src/service/party_orientation_model/` (sem rede, banco nem arquivos), adaptador de arquivos em `src/storage/party_orientation_files.py`, comando em `src/application/party_orientation.py`. Não está ligado ao painel nem ao catálogo de produção (`political_orientation_catalog.json/.py`); a integração depende de aprovação explícita.

## Princípio

O comportamento pesa mais que o discurso. O modelo mede o que o partido vota, implementa, apoia e propõe, e compara com o que diz de si. Pesquisas de especialistas são referência de calibração e nunca entram na pontuação. O resultado não é decidido de antemão: PDT e PCdoB passam pelo mesmo caminho de qualquer partido, e sem evidência a saída é "evidência insuficiente".

## Arquitetura

| Módulo | Responsabilidade |
|---|---|
| `contracts.py` | dataclasses imutáveis, categorias, camadas, erros com código estável |
| `rubric.py`, `rubric_adapter.py` | valida a rubrica; traduz a proposta conceitual de `rubric.json` para o contrato |
| `evidence.py` | valida evidências e sucessões (fonte e data obrigatórias) |
| `applicability.py` | vigência (janela de anos) e linhagem de siglas com fonte |
| `scoring.py` | média por camada, combinação das camadas, intervalo, contribuição por evidência |
| `assessment.py` | suficiência e confiança por dimensão |
| `overall.py` | combina as dimensões |
| `categories.py` | sete faixas, controvérsia, perfil misto, gate de extremos |
| `divergence.py` | discurso x ação, autodeclaração x ação, calibração com especialistas |
| `explanation.py` | explicação por indicador (qual evidência puxou para qual lado) |
| `classifier.py`, `batch.py`, `serialization.py` | orquestração, lotes, JSON auditável |
| `catalog_adapter.py` | converte a saída ao formato do catálogo (pronto, NÃO ligado) |
| `comparison.py` | relatório contra o catálogo |

## Fórmula

Escala de -1 (esquerda) a +1 (direita) por indicador e por dimensão (econômica e sociocultural; o polo sociocultural positivo é tradição/autoridade, e não é "direita econômica").

1. Cada evidência tem `stance` em [-1, +1], camada, indicador, nível de prova, fonte, data e janela de vigência. `oriented_stance = stance x direção do indicador`.
2. Peso da evidência = peso do indicador x multiplicador do nível de prova x fator temporal (x multiplicador de sucessão, se herdada).
3. Fator temporal = sobreposição entre a janela da evidência e o período, dividida pelo menor dos dois comprimentos.
4. Por camada: média ponderada. Dimensão = soma(peso efetivo da camada x média) / soma dos pesos efetivos das camadas presentes.
5. O peso do discurso é limitado a `discourse_cap_ratio` x o peso comportamental presente, então o comportamento sempre supera o discurso, mesmo quando só uma camada comportamental existe.
6. Erro padrão por camada: variância encolhida em direção a um prior (`prior_standard_deviation`) sobre a amostra efetiva; intervalo de 95% = escore +- 1,96 x erro combinado.
7. Escore geral = média das dimensões suficientes pelos `dimension_weights`.

### Pesos (rubrica `APROVADA_2026-10-29`)

Lidos de `rubric.json`: votos 0,30; políticas implementadas 0,25; iniciativa e agenda 0,15 (dividido igualmente por escolha do adaptador entre projetos, políticas apoiadas e foco temático, 0,05 cada); discurso 0,20 (programa/estatuto 0,10, manifesto 0,05, lideranças 0,05). A rubrica atribui 0,10 a estimativas externas; o modelo as mantém com peso 0 e as usa só para calibrar (`expert_calibration`), evitando circularidade (decisão R8, aprovada). Indicadores de direção contestada (E5, E7, E9, C3, C5, C7, C8) têm peso 0: aparecem nas explicações, mas não entram no escore (R6). As 8 decisões estão em `rubric.json`, bloco `approval`. Faixas: +-0,15, +-0,40, +-0,80.

Escolhas que a rubrica não faz estão em `MODEL_PARAMETERS` (`rubric_adapter.py`) e dependem de aprovação: teto do discurso 0,5, multiplicadores de prova (0,4 / 0,7 / 1,0), sucessão 0,7, dimensões 50/50, mínimos de itens/fontes/confiança, limiares de divergência (0,35 por dimensão, 0,50 por indicador, 0,30 de calibração), controvérsia (intervalo cobrindo 4 faixas ou mais). Os mínimos de 4 indicadores econômicos e 3 culturais vêm da rubrica.

## Suficiência, confiança e divergência

- Suficiência por dimensão: número mínimo de itens, itens comportamentais, indicadores distintos, fontes distintas e confiança mínima. Qualquer falha dá `insufficient_evidence`; o escore indicativo aparece só como `indicative_score_not_for_use`. Exigem-se as duas dimensões.
- Confiança (0 a 1) = média ponderada de quantidade, cobertura das camadas, concordância entre evidências e precisão do intervalo; rótulos baixa/média/alta.
- Divergência: discurso x comportamento por dimensão e por indicador, autodeclaração x comportamento geral, e a distância ao valor dos especialistas. Cada registro traz direção, gravidade e as evidências dos dois lados.

## Vigência e sucessões

A classificação é por partido e período (legislatura ou ano). Evidência fora da janela é excluída com motivo. Sigla anterior só vale para a sucessora com registro em `successions.json` (fonte e data), apenas para evidência até o ano da sucessão e com peso reduzido; a sucessora nunca volta ao passado da antecessora.

## Categorias

`extreme_left`, `radical_left`, `left`, `center_left`, `center`, `center_right`, `right`, `radical_right`, `extreme_right`, `mixed_profile` (dimensões em lados opostos, conforme a opção da rubrica), `controversial`, `insufficient_evidence`. A intensidade (|escore| >= 0,80 em ao menos uma dimensão) dá apenas `radical_*`. `extreme_*` exige o gate democrático: marcadores G1 a G4 em evidência com prova suficiente, revisada por pessoa (`human_reviewed`), de ao menos duas fontes independentes e ao menos uma primária, sem herança de sigla. Rótulo da imprensa, ato isolado de parlamentar ou escore alto não bastam.

## Como adicionar evidência

Crie um arquivo com `schema_version: party_orientation_evidence.v1` e a lista `evidence` em `evidence/<camada>.json` (os arquivos dos coletores, em outros esquemas, nunca são sobrescritos nem interpretados). As camadas coletadas são convertidas por `se-liga-brasil build-party-orientation-evidence` (ver `docs/partidos-evidencias-conversao.md`). Campos: `evidence_id` único, `political_party` (sigla vigente na data), `layer` (`votes`, `implemented_policies`, `supported_policies`, `bills`, `thematic_focus`, `discourse`, `expert_survey`), `dimension`, `indicator_id` (da rubrica), `stance`, `source_id`, `source_url`, `source_date`, `year_start`, `year_end`, `proof_level`, `attribution_basis`, opcionais `extreme_markers`, `human_reviewed`, `policy_reference_id`. Autodeclaração geral e pesquisa de especialistas usam `dimension: overall` e os indicadores `self_declared_position` e `expert_position`. Arquivos em outro esquema são listados como ignorados, nunca interpretados.

## Como auditar

```
se-liga-brasil classify-political-parties --party PDT,PCdoB --period 2019-2022
se-liga-brasil classify-political-parties --all --comparison-report docs/partidos-modelo-comparacao-catalogo.md
```

Saída em `data/political-orientation/party-model/output/<political_party_id>/<periodo>.json` e `index.json`. Cada JSON traz categoria, escore e intervalo por dimensão, confiança, evidências usadas (peso, contribuição, fonte, data, prova), excluídas (motivo), explicação por indicador, divergências, limitações, versões e `input_digest_sha256`. Mesmos arquivos de entrada geram bytes idênticos. Os testes em `tests/test_party_orientation_*.py` usam apenas fixtures fictícias.
