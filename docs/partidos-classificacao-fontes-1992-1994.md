# Partidos do Senado em 1992–1994: autodeclaração, estimativas e classificação

Revisão de 28/10/2026. Escopo: todos os partidos com cadeira nas fotografias de 31/12/1992, 1993 e 1994 (PMDB, PFL, PSDB, PDT, PT, PTB, PSB, PRN, PDS, PPR, PP e PDC) e partidos relevantes na base dos governos Collor e Itamar (PL, PCdoB, PPS, PSC, PTR, PST, PRONA, PSD e PMN). Registro completo por partido: `data/political-orientation/party-orientation-evidence-1992-1994.json`. Fontes baixadas, com hash: `data/political-orientation/party-sources-1992-1994/` e `manifest.json` (a pasta `data/` não é versionada). Módulo integrado: `src/service/political_dashboard/senate_orientation_1992_1994.py` e `.json`.

## Regra: três coisas que nunca se misturam

1. **Autodeclaração**: o que o partido disse de si em manifesto, programa, estatuto ou declaração de líder. Vai em `self_identification` e não altera pontuação. Cada registro diz se o texto foi citado de documento do partido ou apenas relatado por fonte secundária (o verbete do CPDOC).
2. **Estimativa de pesquisas com parlamentares ou especialistas**: onda, escala, valor, erro padrão e N. Vai em `expert_estimates`. Só as estimativas numéricas definem os grupos.
3. **Autoposicionamento dos membros** na pesquisa de 1993 (campo `LRCLASS`): resposta individual de parlamentares com n pequeno; vai em `member_self_placement_survey`, não é autodeclaração do partido.

Regra de grupo (editorial do projeto, não categoria dos autores): esquerda abaixo de −0,1, centro de −0,1 a +0,1 inclusive, direita acima de +0,1, escala −1 a +1 da onda de 1993.

## Fontes de estimativa efetivamente obtidas

| Fonte | O que traz | Uso |
|---|---|---|
| Zucco e Power (2024), suplemento, Tabela C1 | estimativas −1 a +1 por onda (1990, 1993…), erro padrão | pontuação principal |
| Power e Zucco (2009), dados do Dataverse (hdl:1902.1/11567: `party.estimates.csv`, dados individuais, guia, apêndice) | mesma pesquisa em escala 1–10 reescalonada; respostas individuais de 1990 (249 respondentes) e 1993 (185) | confirma a onda, os itens avaliados (PPR e PP separados em 1993; PDS só em 1990) e o N por partido |
| Coppedge (1997), WP 244, Apêndice A (Brasil 1945–94) | classificação categórica de Ames, Fleischer, Mainwaring e Power | checagem independente de lado |
| Mainwaring, Meneguello e Power (1999), WP 264 | lista qualitativa de partidos de direita e centro-direita; descrição das pesquisas de Power (N 249/185/162) | checagem independente; a Tabela 9 vem em branco no PDF obtido |
| Lucas e Samuels (2010), Tabela 1 | ordenação convencional baseada em Power e Zucco (2009) | fonte secundária |
| CPDOC/FGV, verbetes dos partidos | manifestos e programas (autodeclaração) | autodeclaração |
| Programa e estatuto do PFL de 1999 | texto do próprio partido, posterior ao recorte | autodeclaração, com ressalva |

Não obtidos (registrados como `unavailable` no manifesto, sem conteúdo inventado): Power e Zucco (2009) e (2012) em texto completo (paywall; os dados foram obtidos pelo Dataverse), livro de Mainwaring, Meneguello e Power (2000), Rodrigues (1987), Kinzo (1993), Bresser-Pereira (1988, HTTP 404), tese da UFSCar sobre o PSDB, V-Party, Manifesto Project e Chapel Hill Expert Survey (nenhum baixado nem usado; cobertura de 1992–1994 não confirmada) e Wiesehomeier e Benoit (2009, pesquisa de 2005–2007, fora do período). Baker/Greene e Singer tratam eleitores, não partidos no período, e não foram usados.

## Tabela: partido × autodeclaração × estimativa × classificação final

Valores: Zucco e Power (2024), onda de 1993, −1 a +1 (erro padrão); entre parênteses o n de avaliadores do item na pesquisa de 1993 (arquivos de 2009). Coppedge (1997): SR direita secular, SCR centro-direita, SC centro, SCL centro-esquerda, SL esquerda, P personalista. Cadeiras: 1992 / 1993 / 1994.

| Partido | Autodeclaração (fonte) | Estimativa de 1993 | Coppedge 1997 | Classificação final | Status |
|---|---|---|---|---|---|
| PMDB (MDB) 26/27/23 | "assumiu a posição de centro no espectro político-partidário" (CPDOC, relato; programa de 1996 não obtido) | −0,022 (0,034), 173 | SC | centro | classificado, com ressalva de limiar |
| PFL (DEM) 14/12/12 | liberal; "liberalismo social" (programa/estatuto de 1999, posterior ao recorte); CPDOC: "inspiração liberal e atuação pragmática" | 0,671 (0,038), 166 | SR | direita | classificado |
| PSDB 6/6/8 | manifesto de 1988: confluência de liberais-progressistas, democratas-cristãos, sociais-democratas e socialistas-democráticos (via CPDOC); o CPDOC lê a pretensão como centro-esquerda | −0,225 (0,033), 165 | SCL | esquerda (centro com corte de 0,25) | classificado, sensível ao limiar |
| PDT 4/3/4 | "defesa da democracia, do nacionalismo e do socialismo" (manifesto de 1980, via CPDOC) | −0,447 (0,035), 166 | SCL | esquerda | classificado |
| PT 1/1/1 | "socialista e democrático" (CPDOC sobre o manifesto de 1980) | −0,830 (0,039), 166 | SL | esquerda | classificado |
| PTB 8/5/4 | oposição "patriótica e não demagógica", aberta ao empresariado (Ivete Vargas, 1979–80, via CPDOC); sem rótulo ideológico | 0,482 (0,036), 161 | SCR | direita | classificado |
| PSB 1/1/0 | "aspirações socialistas do povo brasileiro" (manifesto de 1985, via CPDOC) | −0,746 (0,037), 165 | SL | esquerda | classificado |
| PRN 5/4/2 | "liberal democrático" (programa de 1989, via CPDOC) | 0,869 (0,042), 158 | P (personalista) | direita | classificado, com divergência |
| PDS 4/0/0 | "partido da reforma e da transformação", "democracia social" (manifesto de 1980, via CPDOC) | 0,734 pela série PP (ver abaixo); PDS direto em 1990: 0,881 (213) | SR | direita | classificado via série sucessora |
| PPR 0/5/6 | Maluf, 1993: "grande partido progressista, de centro, comprometido com as reformas" (via CPDOC) | 0,734 (0,040), 162 (item PPR) | SR (1994) | direita | classificado via série sucessora |
| PP (1993) 0/1/2 | buscou imagem "socialdemocrata" (CPDOC) | 0,339 (0,035), 157 | SCR | direita | classificado |
| PDC 3/0/0 | "terceira via política" entre liberalismo e marxismo (1985, via CPDOC) | sem estimativa em 1993; 1990: 0,622 (205) | SCR (1986–90) | sem classificação | sem estimativa para o período |
| PL | "seguidor da doutrina liberal" (manifesto, via CPDOC) | 0,643 (0,037), 163 | SR | direita | classificado (sem cadeira atual) |
| PCdoB | objetivo socialista por revolução proletária (CPDOC, histórico) | −0,946 (0,040), 162 | SL | esquerda | classificado (sem cadeira atual) |
| PPS | não obtida | −0,597 (0,036), 155 (coluna CID) | SL (1994) | esquerda | classificado (sem cadeira atual) |
| PSC, PTR, PST, PRONA, PSD (1987), PMN | PSC, PRONA, PSD: sem rótulo; PTR: pontos de programa; PMN: movimento nacionalista, terceiro-mundista | nenhuma | XC (PSC, 3/5), SCR (PTR, PST), SR (PRONA, PSD), PMN só em Mainwaring et al. (centro-direita) | sem classificação | sem escala numérica |

### Pontos que divergem ou exigem inferência

- **PDS e PPR.** A pesquisa de 1993 avaliou o item PPR (162 avaliadores, média bruta 7,75 em 1 a 10) e o PP novo separadamente; o PDS só foi avaliado em 1990. A coluna "PP" de 2024 não é descrita pelos autores como PPR: a associação é inferência do projeto, apoiada em a linha "PPB" do arquivo de 2009 usar o item PPR em 1993 e em as duas fontes terem a mesma ordem relativa (PRN > PPR > PFL > PL > PTB > PP novo > PMDB). Por isso o mapeamento mudou de "leitura editorial por descendência" para "série sucessora inferida", com o item PPR avaliado de fato. Direita em qualquer das duas leituras, e o cenário que remove PDS e PPR da classificação continua na sensibilidade.
- **PRN.** Coppedge o trata como personalista; Mainwaring et al. o contam como conservador; o programa se diz liberal democrático. Nenhuma fonte o põe fora da direita, mas a natureza ideológica é contestada. Novo cenário na sensibilidade.
- **PMDB.** Centro nas duas fontes, a −0,022; a estimativa sobe em ondas posteriores e Mainwaring et al. reconhecem facção conservadora. Resultado depende de aceitar o limiar de 0,1.
- **PSDB.** Esquerda pelo corte do projeto, centro com ±0,25; Coppedge: centro-esquerda; a autodeclaração não é de esquerda. Coppedge registra o rótulo "Social Democrático Brasileiro 1990–94", cuja identificação com o PSDB é provável, não explícita.
- **PDC.** Todas as fontes apontam centro-direita ou direita, mas nenhuma cobre a legislatura de 1991–95. Segue sem classificação.
- **Autodeclaração de centro de partidos de direita.** Mainwaring et al. mostram que membros de partidos conservadores se posicionam à esquerda de onde os demais os situam ("My party may be conservative, but I am not"). Registrado, não corrigido: o grupo vem da estimativa.

## Efeito nas contagens e na conclusão

As pontuações e grupos dos partidos com cadeira não mudaram; mudaram a justificativa de PDS/PPR, o registro de autodeclaração e a checagem categórica. As contagens principais (direita / centro / esquerda / sem filiação / partido sem estimativa / partido não identificado) permanecem:

| Data | Direita | Centro | Esquerda | Sem filiação | Sem estimativa | Não identificado |
|---|---|---|---|---|---|---|
| 31/12/1992 | 31 | 26 | 12 | 2 | 3 | 7 |
| 31/12/1993 | 27 | 27 | 11 | 3 | 0 | 13 |
| 31/12/1994 | 26 | 23 | 13 | 4 | 0 | 15 |

Novo cenário: PRN sem classificação (direita / esquerda: 26 / 12 em 1992, 23 / 11 em 1993, 24 / 13 em 1994), sem maioria. Os demais cenários não mudam. Conclusão de maioria mantida: nenhuma data tem 41 cadeiras de direita ou de esquerda pela classificação adotada; só o MDB lido como direita (e, em 1994, todas as lacunas somadas à direita: 41) produziria maioria, o que é limite superior e não resultado.

## Lacunas

- Texto completo do estatuto e programa de 1992–94 de cada partido (TSE) não foi obtido; autodeclarações vêm de manifestos de fundação citados pelo CPDOC, exceto o PFL de 1999.
- A Tabela 9 de Mainwaring et al. está em branco no PDF obtido; os valores brutos de 1990 e 1993 foram recalculados dos dados individuais de 2009 (`derived-power-zucco-2009-raw-party-ratings.json`, derivado local, não fonte primária).
- PDC, PSC, PTR, PST, PRONA, PSD e PMN continuam sem escala numérica para 1991–95.
- Os rótulos de partido ainda não identificados nas cadeiras dependem da reconciliação com o banco, feita em outra frente. PL, PCdoB e PPS já têm pontuação no módulo para o caso de aparecerem; `KNOWN_LABELS` em `scripts/build_senate_orientation_1992_1994.py` hoje descarta esses rótulos e precisaria ser ampliado junto com essa reconciliação.
