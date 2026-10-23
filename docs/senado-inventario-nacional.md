# Inventário nacional de parlamentares do Senado

A busca pública por cargo depende de mandatos e exercícios institucionais comprovados.
Ela não usa a candidatura eleitoral para afirmar que alguém está exercendo um cargo.
Consequentemente, enriquecer apenas as pessoas já importadas do TSE não garante a
presença dos atuais senadores de todas as unidades federativas.

## Fontes oficiais

- [Parlamentares atualmente em exercício](https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json):
  informa a composição observada, mandato, capacidade e períodos de exercício.
- Perfil individual: `https://legis.senado.leg.br/dadosabertos/senador/{codigo}.json`:
  informa nome civil completo, nome parlamentar e data de nascimento.

Na observação de 22/10/2026, a lista oficial continha 81 pessoas em exercício:
70 titulares e 11 primeiros suplentes. Esse total é uma observação da fonte, não
uma constante usada para fabricar ou completar registros.

## Coleta e identidade

O coletor nacional não exige candidatura prévia na base. Cada lote baixa no máximo
25 perfis, usando o cache imutável, a política de espera e os locks compartilhados
dos demais coletores do Senado. O artefato agregado referencia a lista e o perfil
individual, incluindo seus respectivos hashes.

A resolução canônica reutiliza a regra compartilhada de nome civil completo e data
de nascimento únicos. CPF ausente continua ausente. Código parlamentar identifica
o sujeito na fonte, no namespace `senator`, e não é uma identidade pessoal global.
Ambiguidade é rejeitada para revisão; uma ponte já existente incompatível provoca
rollback do artefato. Nome parlamentar e nome civil permanecem distintos.

O mandato e o período efetivo de exercício são projetados separadamente. A entrada
de um suplente não transforma todo o mandato em exercício. Remuneração não faz
parte deste job.

## Execução de um lote

```sh
.venv/bin/python scripts/collect_senado_roster.py \
  --env-file /caminho/para/.env --limit 10 --offset 0
```

Repita com offsets seguintes e `--limit` de até 25, usando a mesma lista em cache.
Os retornos de ingestão distinguem registros novos, reaproveitados e rejeitados.
Após cada lote, a projeção pública é atualizada.

O primeiro diagnóstico está em
`data/enrichment/audits/senate-roster-coverage-20261022.json` (artefato operacional
local, não versionado). Ele encontrou somente cinco canônicos compatíveis com a
lista oficial; as candidaturas carregadas até então abrangiam apenas SP e RJ.

## Validação

Os testes institucionais verificam nome civil/nome público, nascimento obrigatório,
coerência entre perfil e lista, suplência, limites de lote, criação sem candidatura,
reaproveitamento de identidade e rejeição de conflito. Os testes SQL usam esquema
isolado com rollback obrigatório. Há regressão para uma mesma observação partidária
processada por dois artefatos, evitando intervalo de validade com duração zero.
