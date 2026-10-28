# Histórico de prefeituras

```sh
PYTHONPATH=src .venv/bin/python scripts/collect_municipal_government_history.py
```

A coleta gera `data/municipal-government-history/historical-executive-evidence.json` com
`institution_code=municipal_government` e código IBGE municipal em `territory_code`.
Os identificadores de pessoas são qualificados pela fonte, sem vínculos canônicos ambíguos.
Downloads íntegros são reutilizados por hash/cache; o transporte compartilhado limita tamanho,
frequência e tentativas. A página pública consulta os anuários materializados, sem rede remota.

## Fontes executadas

- Dossiê de Prefeitos da Cidade de São Paulo, Câmara Municipal, revisão de 30/08/2023:
  `https://www.saopaulo.sp.leg.br/documentacao/wp-content/uploads/sites/34/2023/08/Dossie-PrefeitosLista2023.pdf`.
  Datas de titulares desde1899 e substituições temporárias documentadas. A versão e a quantidade
  de mandatos são validadas; nova estrutura exige revisão do parser.
- Arquivo Geral da Cidade do Rio de Janeiro, quadro de governantes: períodos municipais
  desde1975. Governadores da Guanabara não são incorporados como prefeitos.
- Instituto Pereira Passos, cronologia Armazenzinho: a página pública referencia diretamente
  `https://siurblab.rio.rj.gov.br/armazenzinho/pages/reguaTempo/data/timeInfos.json`.
  Esse JSON oficial comprova afastamentoCrivella e exercícioJorgeFelippe em22/12/2020.
- PrefeituraRio: possePaes2025, sucessãoPaes/Cavaliere20/03/2026 e observaçãoCavaliere11/09/2026.
- Catálogo de Legislação deSãoPaulo: Decreto65.606/2026 confirma exercícioNunes em01/10/2026.

## Limitações preservadas

A existência de um nome em um acervo ou um resultado eleitoral não comprova exercício.
O carrosselARQUIP, por exemplo, não é convertido automaticamente em períodos no cargo.
A compilação municipal de2025 também contém divergência de ano em relação à posse do vice;
o dossiê cronológico tem prioridade e a compilação permanece evidência arquivada para revisão.

Não se inventa dia/mês para os quadros anuais. Exercícios abertos só aparecem até sua
observação comprovada. Interinos documentados são retirados dos intervalos do titular,
inclusive em exercícios abertos. As substituições são agrupadas por território e instituição.
Assim, interino de uma cidade não interfere no titular de outra. Em31/12/2021 a evidência
apontaMiltonLeite como prefeito em exercício deSãoPaulo.

Filiações históricas permanecem desconhecidas quando não comprovadas. Substituições com
horários, divergências internas das listas de interinos e interinos não encontrados mantêm
cobertura parcial. Isso não deve ser divulgado como histórico integral ou filiação contínua.
O cargo de prefeito deSãoPaulo foi recriado em1898, com exercício desde1899; não se inventam
prefeitos para1889–1898. ParaRio, a cobertura desta etapa começa na fase municipal de1975.
