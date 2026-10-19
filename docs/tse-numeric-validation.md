# Validação de valores monetários do TSE

## Diagnóstico de 16 de outubro de 2026

As quatro rejeições `INVALID_MONEY` da validação `tse-python-v3` do recurso de bens de 2026 não representam quatro números malformados. São duas declarações distintas, repetidas nos arquivos nacional e estadual de SP:

- `-491,27`: linhas 66864 de `bem_candidato_2026_BRASIL.csv` e 1272 de `bem_candidato_2026_SP.csv`.
- `-1199,67`: linhas 67136 e 1544 dos mesmos arquivos.

Ambas têm código de tipo de bem 61. Não é possível inferir dívida, erro de declaração ou outra semântica apenas pelo sinal. Nenhum nome, documento ou identificador de pessoa é necessário para reproduzir o problema.

Arquivo local: `data/tse/archives/2a8028ccc993c364031dbaa300e35e1e638ea1626f1e486f61d591b84ab2f3a3.zip`.
Fonte oficial: https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2026.zip
O manifesto registra aquisição em 7 de outubro de 2026; esta investigação usa o arquivo adquirido, sem presumir que representa a versão mais recente da fonte.

## Tratamento implementado

`normalization.scalars.normalize_money` recebe `allow_negative=True` quando a fonte permite números com sinal. O padrão permanece não negativo. A sintaxe e a semântica estão separadas: `INVALID_MONEY` identifica formato inválido; `NEGATIVE_MONEY_NOT_ALLOWED` indica número válido que viola uma política não negativa.

O adaptador TSE preserva o valor com sinal e acrescenta `declaredValueQuality: negative_requires_review` somente às declarações negativas. Valores positivos mantêm o payload anterior, evitando versões artificiais no histórico. Não se aplica valor absoluto e não se converte negativo em zero. `-0,00` normaliza para `0.00`, sem sinal monetário efetivo.

A integração no banco exige migrar a constraint não negativa de `candidate_asset_declaration`, persistir o status de qualidade e impor consistência entre sinal e status. A versão do parser deve ser incrementada para invalidar os resultados de validação armazenados. A reexecução usa a chave da declaração para consolidar a evidência BRASIL/SP; quatro linhas não devem produzir quatro declarações.

## Reutilização por outras fontes

Exemplo para folha com separador brasileiro:

```python
normalize_money("-1.199,67", allow_negative=True, missing_values=frozenset({""}))
```

`missing_values` permite definir os marcadores de ausência de cada fonte. O padrão preserva as sentinelas legadas TSE (`-1`, `-3`, `-4`, entre outras). Fontes como ALESP podem removê-las: o número inteiro `-1` pode representar dinheiro nessas fontes. Marcadores reais de ausência devem ser definidos explicitamente pelo adaptador. A opção também está disponível em `normalize_text`.

Não se adivinha localidade. Vírgula decimal aceita agrupamento brasileiro estrito (`1.234,56`); ponto decimal exige `decimal_separator="."` e não aceita separadores de milhar. Notação científica, NaN, infinito, múltiplos sinais, agrupamento inválido e mais de duas casas continuam rejeitados. Valores permanecem strings decimais exatas; não há float ou arredondamento silencioso.

## Verificação e revisão

- 28 testes focados em `tests/test_normalization.py` e `tests/test_numeric_validation.py` passam, incluindo exemplos reais anonimizados, qualidade somente em negativos, sentinelas e formatos inválidos.
- Varredura somente leitura de 26.055 linhas SP/RJ dos arquivos BRASIL e SP: zero erros de formato após o ajuste, quatro ocorrências negativas e duas declarações negativas distintas. Esta verificação de formato inclui todos os cargos desses arquivos, não somente o escopo de cargos da carga.
- Ruff e revisão estrutural não apontaram achados nos arquivos alterados.
- Revisão semântica: normalização pura, política de sinal explícita por fonte, origem preservada e nenhum acesso remoto ou ao banco. Custo O(m) em tempo e memória por valor de m caracteres; varredura O(n) em registros, em streaming. A migração e o teste de ingestão devem comprovar a preservação no banco antes da carga.
