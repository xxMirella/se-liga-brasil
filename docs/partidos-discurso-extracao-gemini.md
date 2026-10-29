# Extração de evidências de discurso com o Gemini (piloto PT, NOVO, MDB)

Piloto de 29/10/2026. Lê estatutos, programas e páginas oficiais dos partidos já arquivados em
`data/political-orientation/party-model/discourse/` e extrai **candidatos a evidência** da camada
de discurso. Nada daqui entra no cálculo do modelo: todo item sai com `weight_override: 0`,
`human_reviewed: false` e `review_status: pending_human_review`.

## Como funciona

1. **Texto**: PDF digital (`pdftotext`), HTML (texto de `<p>`, títulos e listas, sem menu/rodapé) ou
   texto de OCR já gerado (`parties/<P>/ocr/*.txt`, marcado como origem `ocr`). PDF sem camada de
   texto e sem OCR é pulado e listado no dry-run.
2. **Segmentação** por artigo/seção, com até 4.000 caracteres por trecho.
3. **Filtro de relevância** por palavras-chave (um conjunto por indicador). Só decide o que vai ao
   modelo; não classifica.
4. **Codificação cega**: sigla, nome do partido, apelidos (petista, emedebista), links e lideranças
   conhecidas viram `[PARTIDO]`, `[LINK]`, `[LIDERANÇA]` antes do envio. Limite: o contexto ainda
   pode revelar o autor (por exemplo "o Presidente [LIDERANÇA]", "o maior partido do Brasil").
5. **Gemini**, temperatura 0, saída em JSON com esquema fixo: indicador (E1–E9, C1–C9, G1–G4 da
   rubrica aprovada), direção (−1, 0, +1, não se aplica), força (1–3), compromisso concreto ou
   genérico e **citação literal**. O prompt tem versão (`discourse-extraction.v1`).
6. **Validador determinístico**: descarta o item se a citação não existir, palavra por palavra
   (ignorando só espaços e aspas/travessões tipográficos), no trecho enviado; também descarta
   indicador/direção/força inválidos, citações curtas e duplicatas.
7. **Duas execuções independentes** por trecho. Cada item da primeira é marcado `agree`,
   `direction_conflict` ou `single_run`; divergências vão para revisão prioritária.
8. **Saída** em `discourse/extractions/<PARTIDO>/<hash12>__<modelo>.json` (proveniência: modelo,
   versão do prompt, hash do documento, data) e `evidence_pending_review.json` no contrato
   `party_orientation_evidence.v1` (camada `discourse`). Indicadores de direção contestada
   (E5, E7, E9, C3, C5, C7, C8) levam `display_only: true`.

Código: `src/gemini_api/` (adaptador: cliente, ritmo, repetição com espera, cache em disco por
hash de modelo + versão do prompt + execução + texto) e `src/service/party_discourse_extraction/`.
Script: `scripts/extract_party_discourse.py` (**dry-run por padrão**; `--apply` faz chamadas).

## Como rodar

```
# estimativa (sem chamadas)
.venv/bin/python scripts/extract_party_discourse.py
# amostra pequena, depois tudo; retoma sozinho pelo cache
.venv/bin/python scripts/extract_party_discourse.py --apply --model gemini-3.5-flash-lite --limit 5
.venv/bin/python scripts/extract_party_discourse.py --apply --model gemini-3.5-flash-lite
```

A chave fica em `GEMINI_API_KEY` num `.env` (o do projeto ou o de
`mdqc-knowledge-center`); nunca é impressa nem gravada (vai só no cabeçalho `x-goog-api-key`).

## Plano gratuito: o que verificamos (29/10/2026)

- **Termos**: no plano gratuito o Google pode usar entradas e respostas para melhorar produtos e
  revisores humanos podem lê-las; recomenda não enviar dados pessoais ou confidenciais. Os
  documentos do piloto são **públicos e oficiais dos partidos** (estatutos registrados no TSE,
  programas e páginas institucionais) e vão com o partido oculto, então o uso é aceitável.
  **Não enviar** dados pessoais, documentos internos ou conteúdo de terceiros por este caminho.
- **Cotas** (por projeto, por modelo; valores só no AI Studio): `gemini-3.5-flash` deu 429 de
  **20 pedidos por dia** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), com reinício à
  meia-noite do Pacífico. O `gemini-3.8-flash` ficou instável (503/timeout) e o `2.5-flash` não
  está mais disponível para contas novas. Os modelos `flash-lite` têm cota própria e foram usados
  para o piloto completo.
- **Qualidade**: `flash-lite` não "pensa" (rápido, barato), mas é o mais fraco. O resultado precisa
  ser lido como candidato a evidência, não como medida.

## Resultado do piloto (`gemini-3.5-flash-lite`, 29/10/2026)

- 3 partidos, 6 documentos com texto (PT: manifesto; NOVO: 2 estatutos e 1 página; MDB: estatuto
  digital, estatuto por OCR e 2 páginas). O estatuto escaneado do PT ficou de fora (sem OCR ainda).
- 79 trechos relevantes × 2 execuções = 158 chamadas, ~402 mil tokens.
- Itens aceitos na 1ª execução: 35 (PT 19, MDB 10, NOVO 6). Mais 9 itens aparecem só na 2ª.
- Consistência entre execuções: 29 concordam, 0 com direção oposta, 6 só na 1ª e 9 só na 2ª
  (concordância 0,66). O modelo é estável na direção, mas instável sobre *o que* citar.
- Descartes pelo validador: 21 itens (16 citações que não existem no trecho, 3 inutilizáveis, 2
  curtas demais), cerca de um terço de tudo o que o modelo devolveu. Sem o validador, esses itens
  teriam entrado como evidência.
- Candidatos a evidência: 41 (PT 23, MDB 12, NOVO 6; incluem 5 trechos de uma amostra anterior com
  `gemini-3.5-flash`, mantidos em arquivos separados por modelo). Todos com peso 0 e sem revisão.
- Conjunto de rotulagem: o modelo também rotulou os 102 trechos (18 com algum item, 84 sem), em
  `labeling/_interno/ia_rotulos.json`, para a comparação pessoa × IA assim que houver rótulos.

## Limites

- A regeneração do conjunto de rotulagem é bloqueada se `rotulagem.csv` existir: novos textos
  (como OCR) mudam a amostra e os ids. Use `--overwrite-labeling-set` só antes de distribuir.
- Estatutos tratam sobretudo de regras internas; o sinal ideológico está nos programas e
  manifestos, e só PT tem manifesto no piloto. O estatuto escaneado do PT ainda não tem OCR.
- Documentos sem data conhecida usam o ano da coleta (`document_date_known: false`): a validade
  no período só pode ser fixada na revisão humana.
- O cegamento é de melhor esforço (ver acima).
- Duas execuções com temperatura 0 mostram instabilidade do modelo, não correção: concordância
  entre execuções não prova que a leitura está certa. Para isso há o conjunto de rotulagem humana.

## Rotulagem humana

`discourse/labeling/`: `rotulagem.csv` (102 trechos, 34 por partido; partido oculto, ids neutros em ordem
embaralhada), `LEIA-ME.md` (passo a passo) e `_interno/` (chave dos trechos e, depois,
`ia_rotulos.json`; as pessoas não devem abrir). Cálculo de concordância (kappa de Cohen) com
`scripts/compute_labeling_agreement.py`.
