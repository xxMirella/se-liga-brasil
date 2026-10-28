# Histórico de governos estaduais

O coletor `scripts/collect_state_government_history.py` arquiva documentos oficiais e gera
`data/state-government-history/historical-executive-evidence.json`, entrada do agregador anual.
Os arquivos originais, SHA-256, datas de coleta e seletores das passagens ficam preservados.
O catálogo de fontes está em `src/crawlers/state_government/catalog.py`.

```sh
PYTHONPATH=src .venv/bin/python scripts/collect_state_government_history.py
```

A coleta usa o transporte compartilhado do projeto: limites de tamanho, cache de arquivos,
intervalos entre requisições e respeito aos bloqueios temporários das fontes. A interface pública
consulta os anuários materializados; não executa estas requisições governamentais.

## Cobertura inicial executada

- São Paulo: exercícios documentados de 16 de novembro de 1889 a 2026. As cronologias da
  ALESP incluem interinos e o triunvirato provisório. Fontes adicionais comprovam posses,
  renúncias e observações posteriores dos exercícios abertos.
- Rio de Janeiro: registros em todos os anos de 2000 a 2026, com precisão anual em parte dos
  registros e datas completas quando documentadas. Isso não comprova todos os interinos.
- Os vínculos são identificadores qualificados pela fonte. Nenhuma associação nominal
  ambígua com pessoas canônicas é gravada automaticamente.

## Semântica e limites

`ends_before` é exclusivo. A precisão anual nunca recebe dia ou mês inventado. Exercício
aberto possui `observed_through`; não é propagado até hoje apenas porque não há data de saída.
Interinos documentados são separados dos titulares; sobreposições incompatíveis das fontes
continuam sinalizadas como cobertura parcial. Registros de um mesmo dia são preservados.

O partido de uma biografia parlamentar não comprova filiação contínua. O registro da Câmara
sobre Garotinho, por exemplo, não deve ser aplicado automaticamente a todo seu governo.
Somente a passagem explícita do Diário da ALEMA, que documenta a filiação de Alckmin ao PSDB
entre 1988 e 2021, foi promovida a filiação contínua. Rótulos partidários contemporâneos em
atos de posse permanecem observações com sua própria data e fonte. Desconhecido não significa
sem partido. As lacunas de filiação e de interinos mantêm `coverage=documented_partial`.

A precisão e a evidência precisam ser revisadas antes de adicionar períodos em
`verified_periods.py` ou `annual_observations.py`. Os testes protegem contra a extrapolação de
exercícios abertos, a perda dos códigos de cargo históricos e a confusão de partido com cargo.
