# Assiduidade e obrigações do cargo

Não existe uma escala nacional única aplicável a todos os cargos políticos.
A regra pertence à instituição, ao cargo, ao período de exercício e ao tipo de
atividade. Não presumir cinco dias úteis por semana nem usar votos como presença.

## Indicador mensal

Identificar cada agregado por `person_id`, instituição, ano, mês e base de
medição: dias, sessões ou reuniões. Bases diferentes não podem ser somadas.
Guardar unidades exigidas, presenças registradas, faltas justificadas, faltas
sem justificativa e resultados desconhecidos, além da fonte, data de observação,
vigência da regra, cobertura do período e versão do cálculo.

Presença registrada (%) = presenças ÷ unidades exigidas × 100.

Falta justificada não vira presença. Eventual indicador de cumprimento legal
precisa de regra própria e nome separado. Licenças e dispensas só alteram as
obrigações quando a fonte oficial comprovar sua aplicação à pessoa e ao período.
Cobertura incompleta, resultados desconhecidos ou denominador zero não geram
porcentagem. Mês em andamento deve aparecer como parcial, até a data informada.

## Fontes e limites

- Câmara dos Deputados: o Ato da Mesa 191/2017 usa sessões deliberativas com
  Ordem do Dia aberta para a aferição constitucional. O relatório público também
  apresenta frequência por dia. Manter esses dois indicadores separados.
  [Regra oficial](https://www2.camara.leg.br/legin/int/atomes/2017/atodamesa-191-8-junho-2017-785035-normaatualizada-cd-mesa.html).
- Senado, assembleias e câmaras municipais: obter calendário, regra de frequência
  e registros da respectiva casa; não copiar a regra da Câmara federal.
- Presidente, governadores, prefeitos e vices: agenda pública não comprova uma
  jornada completa nem fornece, sozinha, um denominador de frequência. Exibir
  indisponível enquanto não houver obrigação e registros oficiais comparáveis.

No perfil, usar rótulo específico, por exemplo “Presença em plenário”, acompanhado
do mês e de “8 de 10 sessões”. Isso não mede todo o trabalho nem sua qualidade.

## Implementação e execução

`collect-attendance --limit 25 --env-file CAMINHO` descobre integrantes das
legislaturas da Câmara desde 2000, valida a identidade pessoal e processa um lote.
O progresso fica em `data/enrichment/attendance/progress.json`; novas execuções
retomam os perfis pendentes, reaproveitando os downloads. A busca começa na
primeira legislatura encontrada para a pessoa, nunca antes de 2000. A lista de
integrantes não comprova exercício durante todos os dias da legislatura.

O parser confere os dias extraídos contra o total publicado, deduplica o dia e
rejeita conflitos. As consolidações mensais ficam em `person_fact` com evidência
e vínculo ao registro de origem. O perfil consulta essas projeções, sem acessar
fontes externas durante a navegação, e permite abrir o histórico mensal.

O pipeline publica snapshots Parquet no Storage privado, em
`attendance/camara/year=YYYY/month=MM/`, com um registro por pessoa no mês.
O manifesto declara cobertura apenas das pessoas coletadas. Os arquivos originais
permanecem intactos; o identificador da pessoa é sempre o `person_id` interno.

O coletor atualmente cobre frequência diária do plenário da Câmara. Senado,
assembleias, câmaras municipais e Executivo continuam pendentes de integração.
Restrições de acesso e anos sem resposta válida permanecem pendentes; não
certificam ausência de atuação nem cobertura completa desde 2000.
