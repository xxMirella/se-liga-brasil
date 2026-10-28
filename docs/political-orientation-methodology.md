# Classificação política datada do panorama

A primeira versão usa exclusivamente o dataset original de Bolognesi, Codato, Ribeiro e Silva, publicado em2025 no Harvard Dataverse: [Database on the ideological classification of all Brazilian political parties (2018–2022)](https://doi.org/10.7910/DVN/MFIXKW), versão1, licençaCC0. O código de identificação da fonte é o próprio DOI; o arquivo utilizado é `df_experts.csv` (id10898288). O codebook dos autores, `Codebook_experts.docx` (id10898289), define ondas distintas de2018 e2022, escala0–10 e valores ideológicos por partido.

O catálogo contém67 observações:35 partidos em2018 e32 em2022. São médias aritméticas recalculadas das respostas válidas não vazias em cada coluna `ideol_18_*` ou `ideol_22_*`. O catálogo registra coluna original, número de respostas válidas, desvio padrão entre respondentes, score e SHA256 do CSV. O desvio padrão descreve dispersão; não é apresentado como intervalo de confiança nem como probabilidade de um partido pertencer a uma categoria.

A simplificação visual em três grupos é uma regra explícita do Se Liga, Brasil, aplicada à média original: esquerda abaixo de4,5; centro de4,5 a5,5 inclusive; direita acima de5,5. Essas três classes não são atribuídas aos autores como se fossem as categorias originais do levantamento. O módulo devolve a regra e a metodologia junto com cada resultado.

## Limites temporais e semânticos

Uma observação de2018 vale apenas para2018. Uma observação de2022 vale apenas para2022. Não há preenchimento de anos intermediários, extrapolação para2026 ou classificação desde1880. Anos sem observação retornam `undetermined`/“Sem classificação”. Isso é falta de classificação datada disponível, não uma posição de centro.

A classificação é uma estimativa nacional da posição do partido segundo especialistas. Não mede a orientação de cada pessoa, votação, ação de governo, política pública, governo estadual ou prefeitura. Filiação, apoio a um governo e orientação ideológica permanecem conceitos diferentes.

Não há transferência automática entre siglas renomeadas, fusões e incorporações. PR em2018 não vira PL em2018 por conveniência do painel; UNIÃO em2022 não recebe retrospectivamente os scores de DEM ou PSL. A combinação de sigla e ano impede usar o PSD contemporâneo para classificar o PSD de1945. Qualquer expansão exige identidade e período confirmados por fonte própria.

“S/Partido”, “Sem Partido” e “Sem filiação partidária” retornam `unaffiliated`/“Sem filiação”, nunca centro. Informação ausente, filiação não informada e contextos institucionais como partidos proibidos retornam sem classificação. A interface mantém categoria própria para fontes comparáveis que produzam classificações conflitantes; não se calcula uma média entre metodologias incompatíveis para esconder divergência. O catálogo inicial tem uma única metodologia e não contém conflitos ativados.

## Integração

Importar `classify_political_orientation(political_party, year)` de `service.political_dashboard.political_orientation_catalog`. O resultado contém categoria, rótulo, status, versão, fonte, metodologia, ano de referência, score e limitações. O índice é carregado uma vez por processo, com busca por sigla/ano emO(1). Nenhum pedido público acessa o dataset remoto ou respostas individuais.

As constantes `ORIENTATION_METHODOLOGY_URL` e `ORIENTATION_METHODOLOGY_LABEL` estão disponíveis para exibição. O JSON compacto fica no pacote Python e é incluído pelo `package-data`; arquivos brutos e codebook ficam apenas em `data/political-orientation/sources` para reprodução e auditoria.

Reconstrução: `.venv/bin/python scripts/build_political_orientation_catalog.py`. O comando recusa um CSV cujo SHA256 difira do original validado. A expansão futura exige uma versão nova do catálogo e testes de temporalidade e identidade.

## Fontes adicionais avaliadas, ainda não ativadas

- [Artigo original de2023, survey2018](https://doi.org/10.1590/dados.2023.66.2.303): fundamenta a abordagem por especialistas e ressalta sensibilidade temporal. O catálogo inicial reproduz o dataset original de2025, não transcreve valores de uma reprodução secundária da figura do artigo.
- [V-Party versão2](https://v-dem.net/data/v-party-dataset/) e [codebook](https://v-dem.net/documents/6/vparty_codebook_v2.pdf), variável `v2pariglef`: dimensão econômica, observações em datas eleitorais, com modelo de mensuração próprio. Não equivale automaticamente à escala geral0–10 do survey brasileiro e não foi misturada a ela.
- O pacote oficial [V-Dem/vdemdata](https://github.com/vdeminstitute/vdemdata) oferece o V-Party emRData. A conversão e a identificação datada dos partidos brasileiros ainda não foram implementadas nesta versão.
- [Power e Rodrigues-Silveira, estudo original e dados de replicação](https://doi.org/10.7910/DVN/5P03UL),1994–2018: usa ondas do Brazilian Legislative Survey e inclui procedimentos de imputação. Requer distinguir pontuações observadas, ondas utilizadas e imputações antes de integrar; resultados eleitorais municipais não podem ser confundidos com a ideologia de quem efetivamente ocupou o governo.

Não existe nesta entrega classificação histórica comprovada para1880–2017 nem para2019–2021 e2023–2026.

## Ampliação histórica em 28/10/2026

A auditoria nacional em `data/political-orientation/annual-audit-1880-2026.json` e seu relatório Markdown registram cada ano de 1880 a 2026 para Presidência, Senado e Câmara (441 recortes), distinguindo evidência parcial, falta de classificação, composição ausente no acervo, instituição inexistente e suspensão documentada. A classificação partidária quantitativa continua restrita às ondas originais; nenhuma lacuna virou centro ou recebeu interpolação.

O catálogo executivo acrescenta Dilma 2011–2016 como síntese editorial fundamentada em Moreira (2023), cuja análise abrange governos Lula e Dilma de 2003–2016. A validade corresponde ao exercício até 12/05/2016, fim exclusivo, preservando a ausência de classificação do exercício de Temer no mesmo ano. A leitura da fonte não equivale a medição ideológica anual independente.

O filtro de abordagem mostra Parlamento não instalado nos anos completos 1938–1945, para Senado e Câmara, com fonte da história institucional do Congresso Nacional. O ano de transição 1937 não é generalizado. A ausência institucional não atribui orientação ao Executivo.

A pesquisa histórica de partidos está em `data/political-orientation/historical-source-review-1880-1985.md`. Ela documenta limites de fontes e identidades; por exemplo, Liberal imperial não é automaticamente esquerda contemporânea, UDN mudou ao longo de sua história e MDB não representava uma esquerda homogênea. A pesquisa permanece aberta para preencher os recortes ainda pendentes com evidência própria.

## Senado de 2026: aplicação editorial explícita

O módulo `senate_orientation_2026` é uma camada editorial específica, não uma alteração das observações científicas do catálogo. Aplica explicitamente a referência de 2022 às bancadas oficiais de 2026 e identifica no card e na linha do tempo o método, o ano de referência, o limiar de maioria absoluta de 41/81 e a sensibilidade às bancadas de PSD/MDB. A distribuição oficial de 28/10/2026 confere com o snapshot local de 22/10. Resultado neste método: direita 63, esquerda 17, sem filiação 1. Excluindo PSD e MDB da direita: 40/81, sem maioria absoluta. Portanto a maioria é apresentada sempre como resultado condicionado à referência acadêmica adotada, não como consenso sobre a posição atual de cada integrante. A regra não alcança Câmara, outros anos ou o resumo nacional de delegações estaduais. Auditoria, fontes, limites e reprodução: `data/political-orientation/senate-2026-audit-20261028.md`.

### Pesquisa complementar de PSD e MDB em 28/10/2026

O aprofundamento encontrou suporte convergente à inclusão do PSD fundado em 2011 na direita ampla: estudos de especialistas, classificação de André Borges (2023), classificação de Rachel Meneguello publicada em 2026 e declaração de Gilberto Kassab em 21/11/2025. As autodeclarações de centro permanecem registradas. Para MDB há divergência substantiva: centro-direita no survey 2022 e centro em classificações históricas alternativas; não se afirma prova uniforme de que sua bancada seja de direita em 2026.

Os métodos foram aplicados separadamente à mesma composição atual: Meneguello resulta em 53/81 à direita, com MDB/Avante no centro; Borges resulta em 49/81, com MDB/PSDB/Avante no centro. Ambos preservam maioria absoluta sem incluir MDB na direita. Isso não cria medição anual de 2026: Meneguello usa classificação histórica e dados eleitorais até 2022, e Borges agrega diferentes fontes e períodos. O método principal 63/81 e a sensibilidade 40/81 sem PSD/MDB continuam visíveis. A tabela do artigo de Bolognesi et al. distingue médias brutas de 2022 (PSD6,94; MDB6,50) e ponderadas (PSD7,151; MDB6,698); as colunas não são intercambiáveis. Relatório completo: `data/political-orientation/psd-mdb-evidence-review-20261028.md`.
