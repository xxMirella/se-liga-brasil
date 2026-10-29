# Fundamentação conceitual da classificação partidária

Status: PROPOSTA para aprovação. Data: 28/10/2026. Rubrica legível por máquina: `data/political-orientation/party-model/rubric.json`. Fontes e hashes: `data/political-orientation/party-model/concept-sources/manifest.json`.

Este documento não classifica nenhum partido. Define conceitos, indicadores, pesos e limiares, para que as camadas de discurso, votações e políticas/governos alimentem um mesmo motor de pontuação.

## 0. Como ler o nível de verificação

Cada afirmação tem um destes níveis de apoio, também gravados no JSON (`support`):

- **verificada em fonte baixada**: li o texto (V-Party codebook v2, Manifesto Project handbook de 2021, Coppedge 1997, Marks et al. 2006, Norris e Inglehart 2016, Bolognesi et al. 2019, Silva sobre Bobbio).
- **relato secundário**: a fonte original não foi obtida (Bobbio, Levitsky e Ziblatt).
- **conhecimento de literatura, não verificado**: autor ou tese que conheço, mas que não pude confirmar em texto (Downs, Laver e Hunt, Poole e Rosenthal, Mudde 2007, Limongi e Figueiredo, Abranches, Singer, Kinzo, Mainwaring 1999). Devem ser conferidos antes de citação literal.
- **proposta do projeto**: escolha metodológica sem fonte que a fixe (pesos, limiares numéricos).

## 1. Conceitos

### 1.1 Esquerda e direita

- **Critério de Bobbio (1994)**. Pela exposição de Silva (via Bobbio 2011, p. 110), a igualdade é o "único critério que resiste à usura do tempo" para distinguir esquerda de direita. Bobbio também propõe uma segunda ideia: a atitude diante da liberdade separa moderados de extremistas dos dois lados (extrema esquerda: igualitária e autoritária; centro-esquerda: igualitária e libertária; centro-direita: libertária e não igualitária; extrema direita: antiliberal e antiigualitária). Esta segunda parte vem de resenhas, não do livro. O projeto a usa para organizar o portão democrático (seção 4), não como escala.
- **Dimensão econômica (Marks et al. 2006)**: "economic redistribution, welfare, and government regulation of the economy. The Left prioritizes economic equality; the Right prioritizes individual economic freedom." O V-Party (`v2pariglef`) operacionaliza: esquerda quer Estado ativo ("higher taxes, more regulation and government spending and a more generous welfare state"); direita quer "privatization, lower taxes, less regulation, less government spending, and a leaner welfare state."
- **Dimensão sociocultural**: Marks et al. descrevem polos compostos GAL (green/alternative/libertarian) e TAN (traditionalism/authority/nationalism). Registram forte afinidade empírica Esquerda-GAL e Direita-TAN no Ocidente, com quadrantes Esquerda-TAN (o comunismo do Leste Europeu) e Direita-GAL (partidos liberais). Por isso as duas dimensões são pontuadas separadamente.
- **Critério de Coppedge (1997), voltado à América Latina**: posição por classe-alvo e prioridade entre distribuição e acumulação.
  - Direita: herdeiros da elite tradicional, discurso fascista, ou partidos patrocinados por governo militar com mensagem conservadora e autoritária.
  - Centro-direita: eleitorado médio e baixo mais elite, com ênfase em cooperação com o setor privado, ordem pública, moralidade e "priority of growth over distribution".
  - Centro: liberalismo político clássico sem agenda econômica/social saliente, ou governos com políticas divididas sem orientação consistente.
  - Centro-esquerda: justiça e igualdade sem alienar classes média e alta.
  - Esquerda: ideologia ou retórica marxista, prioridade da distribuição, papel forte do Estado; pode admitir violência, mas não necessariamente.
  - Fora do eixo: Personalista, Outro bloco, Desconhecido. Coppedge adverte que nomes como Social, Democrático, Liberal, Trabalhista e Radical não são indicadores confiáveis.
  - Ressalva dele: os termos esquerda e direita "não viajam" entre regiões e épocas. O único elemento comum seria esquerda = mudança, direita = preservação ou retorno ao passado.

### 1.2 Definições operacionais (para o motor de pontuação)

Aplicam-se a cada dimensão (econômica e sociocultural) com score S em [-1, +1] (negativo = esquerda econômica ou polo GAL; positivo = direita econômica ou polo TAN). O sinal segue o da escala já usada no projeto (Zucco e Power, esquerda negativa).

| Categoria | Faixa de S | Leitura operacional |
|---|---|---|
| Esquerda radical | S <= -0,80 | Prioriza fortemente igualdade/Estado (ou polo GAL); nenhuma evidência de antidemocracia exigida nem presumida |
| Esquerda | -0,80 < S <= -0,40 | Comportamento majoritariamente pró-Estado/redistribuição nos indicadores disponíveis |
| Centro-esquerda | -0,40 < S < -0,15 | Inclina-se à esquerda mas combina com posições de mercado ou conciliatórias |
| Centro | -0,15 <= S <= +0,15 | Subtipos: moderado (consistente perto de zero), dividido (indicadores dispersos, SD >= 0,40, que se compensam), liberal-político (baixa saliência econômica e cultural, foco em regras democráticas) |
| Centro-direita | +0,15 < S < +0,40 | Simétrico |
| Direita | +0,40 <= S < +0,80 | Simétrico |
| Direita radical | S >= +0,80 | Intensidade; sem evidência de antidemocracia ainda é "radical", não "extrema" |
| Extrema esquerda / extrema direita | \|S\| >= 0,80 em pelo menos uma dimensão E portão democrático confirmado | Ver seção 4 |

Ausência de dados é "sem classificação", nunca centro. Centro só existe com evidência positiva de posições equilibradas. O limiar de 0,15 é proposta; a regra editorial atual do projeto usa 0,10. A sensibilidade a 0,10, 0,15 e 0,20 deve ser reportada.

### 1.3 Oposição-governo, populismo e fisiologismo não são ideologia

- **Governo ou oposição** descreve poder, não posição. O V-Party mede `v2pagovsup` (0 = parceiro sênior no governo, 1 = júnior, 2 = apoio sem cargo, 3 = oposição) separado de `v2pariglef`. O projeto trata como descritor N1, nunca somado à escala esquerda-direita.
- **Populismo.** Norris e Inglehart (2016), citando Mudde, descrevem o populismo como conjunto frouxo de ideias com traços anti-establishment, autoritários e nativistas. O V-Party mede populismo como média harmônica de anti-elitismo e centralidade do povo (`v2xpa_popul`), separado da escala econômica. Divergência: Norris e Inglehart ligam o populismo ao polo TAN; o V-Party o mede à parte. O projeto adota o V-Party: N2 é descritor, não posição. A definição de Mudde (2004) foi relatada por Norris e Inglehart; o artigo original não foi obtido.
- **Clientelismo e personalismo.** V-Party `v2paclient` mede troca de bens "targeted and excludable". Coppedge mantém "personalist" fora do eixo esquerda-direita. São descritores N3 e N4.
- **Instabilidade de sigla**: a regra do projeto de não transferir classificação entre siglas continua (N6).

## 2. Particularidades brasileiras

Registradas como regras de cuidado, não como julgamento sobre partidos.

1. **Nomes enganam** (Coppedge). "Social", "Liberal", "Trabalhista", "Democrático" não provam orientação.
2. **Direita envergonhada**. Bolognesi, Babireski e Maciel (2019) relatam, citando Pierucci (1987), que após a redemocratização poucos se autoclassificavam à direita, por associação com o regime militar. A autodeclaração é, portanto, viés conhecido; declarações valem menos que atos.
3. **Fisiologismo e "centrão"**. A literatura (Abranches 1988 sobre presidencialismo de coalizão; Limongi e Figueiredo; Mainwaring 1999) sustenta que coalizões e a agenda do Executivo condicionam o voto de partidos de campos diferentes. Estes textos não foram baixados. Consequências no modelo: controle de governo/oposição, descritor N5 (incoerência de coalizão) e peso menor que 100% para comportamento. O centrão é descrito como padrão de troca (N3), não como categoria ideológica.
4. **Partidos de aluguel e fusões**: a Lei 9.096/1995 permite fusão e incorporação (art. 29); programas devem respeitar soberania nacional, regime democrático e pluripartidarismo (art. 2). O texto foi lido via WebFetch (curl falhou) e não está arquivado; conferir os artigos antes de citar literalmente.
5. **Mudanças no tempo**. A unidade é partido × período. Coppedge reconhece que o significado de esquerda e direita muda: nos anos 1960 apoio à democracia era visto como incompatível com esquerda; nos 1980, com extrema direita. Daí o portão democrático datado.
6. **Tradições** (apenas etiquetas descritivas, sem pontuação): trabalhismo, socialismo democrático, comunismo marxista-leninista, social-democracia, liberalismo econômico, liberalismo político histórico, conservadorismo, democracia cristã, integralismo/corporativismo autoritário, nacional-desenvolvimentismo, personalismo regional. A distinção entre cada tradição e os partidos concretos deve vir do CPDOC/DHBB e da pesquisa de cada agente, não deste documento. Cautelas: o trabalhismo combina nacionalismo e proteção ao trabalho sem ser socialista; a democracia cristã e a Teologia da Libertação mostram que religião não define o lado sozinha (Coppedge trata cristão-secular como dimensão própria); nacionalismo econômico apareceu em esquerda e direita.
7. **Regimes**: períodos de proibição partidária ou bipartidarismo exigem tag de contexto antes de comparar.

## 3. Rubrica (resumo; detalhe em rubric.json)

Escala de cada indicador: -1 / -0,5 / 0 / +0,5 / +1. Votos usam fração contínua. Ausente é omitido, nunca zero.

### Dimensão econômica

| ID | Indicador | Polo -1 | Polo +1 | Observação |
|---|---|---|---|---|
| E1 | Privatização e propriedade estatal | mantém ou amplia | privatiza | V-Party; Manifesto 413/401 |
| E2 | Escopo e universalidade do gasto social | expande | limita | V-Party; Manifesto 504/505 |
| E3 | Carga e progressividade tributária | progressiva | regressiva ou reduz capital | codificar incidência |
| E4 | Regulação do trabalho e sindicatos | protege | flexibiliza | Manifesto 701/702 |
| E5 | Previdência (incidência) | contestado | contestado | "reforma" não é proxy; peso 0,5 |
| E6 | Regulação de mercados e planejamento | regula | desregula | cuidado: regulação a favor de incumbentes é N3 |
| E7 | Gasto total e ortodoxia fiscal | expansão | consolidação | contestado, peso 0,5 |
| E8 | Terra e ativos | redistribui | consolida propriedade | direção por Coppedge e igualdade (Bobbio), sem fonte brasileira baixada |
| E9 | Abertura comercial e capital externo | protecionismo | abertura | contestado, peso 0,5; protecionismo é esquerda desenvolvimentista ou direita nacionalista |

### Dimensão sociocultural (-1 = GAL, +1 = TAN)

| ID | Indicador | Observação |
|---|---|---|
| C1 | Direitos de minorias e igualdade (raça, gênero, orientação, indígenas) | V-Party `v2paminor`; Manifesto 503/705/607/608 |
| C2 | Moral tradicional (aborto, família, drogas) | Manifesto 603/604 |
| C3 | Religião-Estado | contestado, peso 0,5; tag cristã preservada |
| C4 | Segurança e justiça criminal | Manifesto 605; ligação com autoridade é inferência do projeto |
| C5 | Acesso a armas | contestado, peso 0,5; polo por convenção do debate brasileiro, não por fonte baixada |
| C6 | Nativismo, imigração, superioridade cultural | V-Party `v2paculsup`/`v2paimmig`; Norris e Inglehart |
| C7 | Meio ambiente e uso do solo | contestado, peso 0,5; não contar duas vezes com E8 |
| C8 | Política externa e soberania | contestado, peso 0,5; subcódigos anti-imperialismo x nacionalismo identitário |
| C9 | Liberdades civis e controles institucionais ordinários | violação grave vai ao portão G |

Aborto, armas, política externa e meio ambiente são onde a direção divergiu mais entre fontes e contextos (seção 6).

### Descritores fora do eixo

N1 governo/oposição; N2 populismo; N3 clientelismo; N4 personalismo; N5 incoerência de coalizão (calculado: dispersão da posição do partido entre governos de sinais opostos); N6 instabilidade de sigla.

## 4. Extremos: critério para não rotular sem evidência

"Radical" (intensidade de posição, S >= 0,80 em módulo) é diferente de "extrema" (rejeição organizacional das regras democráticas). O V-Party coloca "Far-left" e "Far-right" em escala exclusivamente econômica (`v2pariglef`), sem exigência de antidemocracia, o que difere de Bobbio e de Levitsky e Ziblatt. O projeto escolhe a segunda via.

Portão democrático (G), por critério:

- G1 compromisso com eleições livres e pluralismo (V-Party `v2paplur`; falha se <= 1 ou texto/ato claro).
- G2 aceitação da legitimidade de opositores e de resultados eleitorais.
- G3 rejeição da violência política e de organização paramilitar (Lei 9.096 art. 6, em paráfrase).
- G4 ruptura institucional (apoio a golpe, tentativa de subverter ordem constitucional).

Regra: "extrema esquerda/direita" só com |S| >= 0,80 e ao menos um critério G falho com evidência organizacional (direção, programa, estatuto, ato do partido no governo), mais duas fontes independentes datadas (ao menos uma primária: texto do partido, decisão judicial ou relatório oficial) e revisão humana. Não bastam: ato de parlamentar isolado; rótulo da imprensa ou de adversários; autodeclaração "revolucionária" sem atos; pontuação econômica alta; ilegalidade do partido em regime autoritário. A evidência vale para o período e não passa a "herdeiros" de sigla.

A distinção entre direita radical (aceita a democracia) e extrema (a rejeita) é atribuída a Mudde (2007, 2019), não obtido em texto. Confirmar antes de citar.

## 5. Comportamento pesa mais que declaração

Proposta (sem fonte que fixe os números; o projeto os escolhe):

| Classe | Peso | Evidências |
|---|---|---|
| Comportamento | 0,70 | votos nominais 0,30; políticas implementadas em governo 0,25; iniciativa legislativa e agenda (o que quer implementar, temas de foco) 0,15 |
| Declarações | 0,20 | programa/estatuto 0,10; manifesto eleitoral 0,05; discurso de lideranças 0,05 |
| Estimativas externas | 0,10 | pesquisas de especialistas e V-Party, mostradas também separadas (prior e validação) |

Por quê:

1. Declarações são baratas e viesadas no Brasil (direita envergonhada; Bolognesi et al. 2019).
2. Coppedge define a posição relevante como ponto médio entre a imagem projetada em discurso e a imagem mais lenta percebida pelos eleitores. Isso defende ponderar discurso, mas não que ele domine.
3. O V-Party define esquerda e direita econômicas por políticas concretas.
4. Comportamento de governo é contaminado por coalizões e restrições (Coppedge: "all must compromise"), o que justifica não dar 100% ao comportamento e justifica os controles abaixo.

Controles:

- **Dissonância**: se |comportamento - declaração| > 0,5, publicam-se os dois scores e a categoria segue o comportamento; não se tira média.
- **Governo × oposição**: calcular scores em separado; se a diferença > 0,30, marcar "posição condicionada ao papel".
- **Multiplicadores de confiabilidade**: fonte primária 1,0; acadêmica secundária 0,8; imprensa 0,5; menos de 5 observações por indicador 0,5; menos de 3 omite o indicador; direção contestada 0,5.
- **Incerteza**: intervalo por bootstrap; categoria só se >= 80% das reamostragens caem nela, senão "fronteira entre X e Y".
- **Mínimos**: ao menos 4 indicadores econômicos, 3 culturais e uma classe comportamental; senão "dados insuficientes".
- **Saliência** (temas de foco): fração de votos/projetos/trechos por indicador; reportada à parte, não altera o sinal.
- **Sensibilidade obrigatória**: 85/10/5, 70/20/10 e 50/40/10.

## 6. Divergências entre fontes

1. **Critério central**: igualdade (Bobbio); igualdade econômica x liberdade econômica (Marks et al.); classe-alvo e prioridade da distribuição (Coppedge). Decisão: composto econômico, igualdade informa as direções.
2. **Número de dimensões**: Bobbio (igualdade + liberdade), Marks (econômica + GAL/TAN), Coppedge (esquerda-direita + cristão-secular), V-Party (indicadores separados). Decisão: duas dimensões + portão democrático; religião em C3 com tag própria.
3. **O que é extremo**: V-Party (extremo econômico), Bobbio (atitude diante da liberdade), Coppedge (sem categoria extrema; observa que a incerteza sobre partidos personalistas ou clientelistas afasta os extremos). Decisão: portão democrático.
4. **Direção de indicadores**: protecionismo e soberanismo como traço populista/TAN (Norris e Inglehart) versus nacional-desenvolvimentismo de esquerda na América Latina. Marcados como contestados.
5. **Valor da autodeclaração**: Bolognesi et al. (viés) versus Coppedge (imagem conta).
6. **Populismo**: Norris e Inglehart (traço do polo TAN) versus V-Party (medido à parte).
7. **Fisiologismo**: Coppedge diz que governos podem contradizer princípios sem abandoná-los; a literatura brasileira não baixada sugere que o voto é condicionado pela coalizão.

## 7. Lacunas

- Não baixados: Bobbio, Downs, Laver e Hunt, Kitschelt, Lipset, Poole e Rosenthal, Mudde (2004, 2007, 2019), Levitsky e Ziblatt, Budge et al. (RILE), Lowe et al. (2011), CHES (codebook; links 404), Hooghe et al. (2002), Dados 2023 (Bolognesi, Ribeiro, Codato), Power e Rodrigues-Silveira (apenas resumo), literatura brasileira (Kinzo, Rodrigues, Limongi, Figueiredo, Abranches, Singer). Marcados `unavailable` no manifest.
- O handbook do Manifesto lista as categorias mas não diz quais são "de esquerda" ou "de direita"; esse mapeamento (RILE) não foi verificado.
- Sem fonte baixada para as direções de E5, E8, C4 (ligação com autoridade) e C5.
- Cobertura brasileira de CHES, Manifesto e V-Party em 1992-94 não confirmada.
- A Lei 9.096 foi lida via WebFetch, não arquivada.

## 8. Decisões que a usuária precisa aprovar

1. Duas dimensões pontuadas + portão democrático + descritores fora do eixo (aprovado conceitualmente?).
2. Pesos 70/20/10 e a regra de sensibilidade; alternativa mais conservadora (50/40/10) como principal.
3. Limiar do centro (±0,10 atual, ±0,15 proposto, ±0,20) e faixas de 0,40 e 0,80.
4. Rótulo "radical" vs "extrema" e o rigor do portão (duas fontes, uma primária, revisão humana).
5. Se haverá rótulo único (esquerda/centro/direita) ou apenas o perfil em duas dimensões; como exibir "perfil misto".
6. Direções dos indicadores marcados como contestados (E5, E7, E9, C3, C5, C7, C8) e se devem entrar no cálculo ou só ser exibidos.
7. Tratamento de governo × oposição (relatar separadamente ou usar apenas pooled).
8. Se as estimativas de especialistas entram no score (0,10) ou apenas como validação.
