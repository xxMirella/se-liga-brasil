# Plano do painel de composição política

Proposta de página do Se Liga, Brasil, planejada em 22/10/2026. O planejamento não confirma cobertura histórica já coletada.

## Objetivo e recorte

Mostrar a composição partidária do Senado e os partidos que ocuparam os governos e as assembleias legislativas dos estados de São Paulo e Rio de Janeiro, com consulta por data desde 01/01/2000. A data inicial do painel não significa que todas as fontes já cobrem esse período.

O recorte inicial confirmado pela usuária inclui os Executivos estaduais e as assembleias legislativas de São Paulo e Rio de Janeiro (ALESP e ALERJ). Nos governos, distinguir governadores, sucessões definitivas e substituições temporárias. Coligação eleitoral, base de apoio e partido da pessoa no exercício do cargo são conceitos separados.

## Organização da página

- Cabeçalho com seletor de estado (SP ou RJ), data de referência, intervalo histórico e data da atualização das fontes. Filtros preservados na URL para compartilhar a consulta.
- Senado: contagem de pessoas em exercício por partido, total observado na fonte, vagas ou conflitos identificados e cobertura de perfis vinculados. Gráfico de barras com contagens visíveis; visualização por UF como filtro opcional.
- Evolução do Senado: composição partidária no último dia de cada mês, desde 2000, respeitando a cobertura efetivamente reconstruída. Selecionar um mês abre a composição e a relação nominal daquela data.
- Governo do estado selecionado: pessoa em exercício e partido na data selecionada, seguidos de linha do tempo dos períodos de governo. Cada segmento permite consultar início, fim, natureza do exercício e fontes.
- Assembleia do estado selecionado: contagens por partido na ALESP ou ALERJ, relação de parlamentares em exercício e evolução mensal desde 2000, com as mesmas regras de suplência, filiação temporal e cobertura do Senado.
- Histórico estadual por partido: períodos comprovados no governo e ocupações na assembleia apresentados separadamente, com opções de ver por ano ou por gestão. Substituições temporárias permanecem distinguíveis das sucessões definitivas.
- Fontes e cobertura: períodos completos, parciais, conflitantes e ainda não pesquisados. Links de fontes sempre em nova aba.

Cada gráfico terá uma alternativa textual acessível com os mesmos valores. As cores identificam partidos, sem atribuir avaliação de desempenho ou posição sobre governo/oposição.

## Regras de contagem e história

1. Usar a filiação partidária válida na data do exercício, nunca o partido atual para recalcular o passado. A data em que o sistema observou uma informação não prova sua validade desde o início do mandato.
2. Contar uma ocupação efetiva por cadeira/data. Titular afastado e suplente em exercício não podem ocupar a mesma cadeira simultaneamente na contagem. Conflitos de fonte devem aparecer como pendência, sem escolha silenciosa.
3. O total da fonte oficial e a cobertura de cadastro são métricas diferentes. A existência de somente cinco perfis vinculados não autoriza mostrar que o Senado tem somente cinco integrantes.
4. Não substituir filiação desconhecida por ausência de partido. Manter categorias distintas para sem partido confirmado e partido ainda não identificado.
5. Preservar os nomes e as siglas partidárias de cada época. Renomeações, fusões e incorporações precisam de relações explícitas; não reescrever retroativamente a distribuição.
6. Nos governos estaduais, segmentar o exercício quando mudar a pessoa ou o partido. O partido de eleição não comprova filiação durante todo o governo. O mesmo governador pode ter mais de um segmento.
7. Incluir períodos iniciados antes de 2000 que continuavam ativos em 01/01/2000, recortando apenas a exibição.
8. Um intervalo sem dados não significa cadeira vaga, ausência de governo nem ausência de atividade. Nenhum gráfico deve preencher lacunas por interpolação política.

## Fontes e estrutura de dados

- [Dados abertos de senadores](https://www12.senado.leg.br/dados-abertos/conjuntos?grupo=senadores&portal=Legislativo): lista em exercício, perfis, mandatos, exercícios e filiações históricas. Conferir contratos no [catálogo oficial da API](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html).
- [Histórico de governadores da ALESP](https://www3.al.sp.gov.br/historia/governadores-do-estado/governantes.htm): ponto de partida para o histórico paulista; o índice consultado alcança 2011 e precisa de complementação posterior.
- Governos de São Paulo e Rio de Janeiro, respectivos Diários Oficiais e registros de posse, afastamento e sucessão: evidência dos períodos efetivos, inclusive após 2011.
- Dados abertos e registros institucionais da ALESP e ALERJ: composição, mandatos, exercícios, suplências e filiação partidária. A existência de propostas ou candidaturas não comprova ocupação de uma cadeira.
- TSE: resultados e filiação no contexto eleitoral. Dados eleitorais complementam a reconstrução; não substituem atos de exercício ou comprovam sozinhos mudanças partidárias entre eleições.

Reaproveitar pessoas, instituições, mandatos, exercícios e filiações temporais existentes. Antes de adicionar métricas, verificar se há uma chave de cadeira compartilhada por titular e suplente; mandatos identificados apenas por pessoa não bastam para provar ausência de dupla ocupação.

As projeções analíticas devem guardar data de referência, fonte, cobertura e versão de geração. A página consulta resultados pré-calculados ou consultas agregadas em lote; não chama APIs governamentais enquanto a usuária abre o painel. Manter o backend e a renderização em Python, seguindo as regras do projeto.

## Entrega em etapas

1. Completar o cadastro nacional do Senado e reconciliar a composição atual com a lista oficial, incluindo o tratamento de suplências.
2. Adquirir exercícios e filiações históricas, reconstruindo composições mensais desde 2000 com cobertura explícita.
3. Cadastrar os históricos dos Executivos de SP e RJ e das respectivas assembleias, reconciliando mudanças de pessoa, partido e natureza do exercício.
4. Publicar agregados versionados e construir a página com filtros, gráficos acessíveis e consulta dos registros individuais.
5. Validar com fontes oficiais antes de apresentar qualquer período como completo.

## Critérios de aceite e regressão

- As contagens por partido, somadas às categorias explícitas de desconhecido e sem partido, reconciliam com as ocupações comprovadas da mesma data.
- Uma troca de partido altera somente o intervalo posterior comprovado.
- Titular afastado e suplente em exercício não geram dupla contagem.
- Governadores anteriores a 2000 e sucessões durante um ano aparecem corretamente no recorte.
- Partido de coligação não recebe contagem de governo ou cadeira sem ocupante filiado comprovado.
- Resultados históricos não mudam apenas porque a filiação atual foi atualizada.
- Mesmas consultas e mesma versão de dados produzem resultados reproduzíveis.
- Lacunas de identidade, filiação ou exercício permanecem visíveis, sem totais aparentemente completos.
