# Conversão das camadas coletadas para o contrato do modelo

Estado em 29/10/2026. Comando: `se-liga-brasil build-party-orientation-evidence` (só lê arquivos locais; não acessa rede nem banco; não liga nada ao painel ou ao catálogo). Código: `src/service/party_orientation_evidence/` (funções puras por camada), `src/storage/party_orientation_evidence_files.py` (leitura e escrita), `src/application/party_orientation_evidence.py`.

Saída em `data/political-orientation/party-model/evidence/` (fora do git): `votes.json`, `implemented_policies.json`, `expert_survey.json`, `discourse.json`. Cada documento é validado pelo contrato `party_orientation_evidence.v1` antes de ser gravado e traz `conversion_notes` com o que foi deixado de fora e por quê. Mesmas entradas dão os mesmos bytes (exceto `generated_on`).

## O que foi convertido

| Camada | Evidências | Origem | Regras |
|---|---|---|---|
| Votos | 426 | votações nominais temáticas de Câmara e Senado (`thematic_roll_calls`) com votos por partido lidos dos arquivos normalizados | uma evidência por partido e votação; escore = 2 x parcela no polo positivo - 1; mínimo de 3 votantes sim/não; rótulo `S.PART.` descartado; nível `documented_primary`; menos de 3 votações temáticas do partido na dimensão e legislatura = indicativo (`reported`, peso 0,4); governo do dia e concordância com o governo aparecem na descrição (N1 fora da escala) |
| Políticas implementadas | 23 | atos legais verificados no LexML, com direção codificada (+1/-1) e partido único do presidente | `documented_secondary` (a direção foi proposta pelo coletor e não teve revisão humana); governos de coalizão (Itamar) e presidente sem partido não são atribuídos |
| Especialistas | 127 | Bolognesi 2018/2022 (catálogo atual) e Power e Zucco 1990-2005 | só `overall`, peso 0, calibração; sigla da própria pesquisa |
| Discurso | 3 | autodeclarações explícitas lidas de citações literais (NOVO direita; PSOL e UP esquerda/socialismo) | só `overall`; a citação precisa existir no arquivo do partido; leitura automatizada, sem revisão humana |

## O que NÃO foi convertido

- **Eixos de PCA (D1/D2):** D1 mistura ideologia e governo x oposição (correlação +0,99 na 56ª e -0,81 na 57ª legislatura) e em 2003-2014 coalizões juntam partidos de lados opostos. Não entra, nem como apoio.
- **Coesão, concordância com o governo e orientação de líderes:** descrevem disciplina, não ideologia.
- **Votações processuais:** requerimentos de urgência ou preferência (Senado 21162-4941 e 404301-6835) ficam fora; a proposição de biossegurança de 2005 é composta (transgênicos e células-tronco) e leva um aviso na descrição.
- **Projetos de lei por tema:** medem foco, não direção. **Itens qualitativos do CPDOC (12):** 7 só do PDT e quase todos anteriores a 1995, o que distorceria a comparação. **TSE (eleitos e coligações):** não são política implementada.
- **Discurso por palavra-chave:** não revisado (`rubric_pending`); PDT e PRD escaneados dependem de OCR.

## Sucessões de sigla (`successions.json`)

Só as com fonte localizada: PFL>DEM (2007, CPDOC), PPR e PP>PPB (setembro de 1995, CPDOC; o dia não consta), DEM e PSL>UNIÃO (08/02/2022, TSE), PR>PL (maio de 2019, TSE) e PRB>REPUBLICANOS (15/08/2019, decisão do TSE). As páginas do TSE devolveram 403 à leitura automática; as datas vêm dos resumos da busca e de fontes secundárias, registrados em `source_note`. Pendentes, sem fonte datada localizada: PMDB>MDB, PPB>PP (2003), PPS>CIDADANIA, PTN>PODE, PL+PRONA>PR. O PL posterior a 2019 é o antigo PR, não o PL anterior a 2006.

## Resultado

520 combinações partido-período: **520 "evidência insuficiente"**. Nenhum rótulo extremo ou radical, nenhuma mudança de categoria em relação ao catálogo, e a sensibilidade 85/10/5 e 50/40/10 não altera nada (não há classificação a alterar). O motivo é cobertura, não método: a rubrica exige 4 indicadores econômicos, 3 socioculturais, 6 itens e 2 fontes por dimensão, e há 28 votações temáticas no total (1 a 7 por legislatura), dez delas em indicadores com peso 0. Os mínimos não foram afrouxados.

O relatório `docs/partidos-modelo-comparacao-catalogo.md` lista, para cada combinação com algum item pontuável, o escore indicativo (NÃO usar). Para PDT e PCdoB, em 2019-2022: PDT econômico -0,08 (2 indicadores, 4 itens), PCdoB -1,00 (2 indicadores, 3 itens); socioculturais sem itens. Nenhum dos dois alcança o mínimo.

## Para chegar a classificações

Faltam evidências, não código: (1) mais votações temáticas, sobretudo socioculturais (casamento, aborto, segurança e liberdades civis); (2) direção codificada e revisada dos projetos de lei; (3) política implementada de partidos que governaram estados e municípios, não só a Presidência; (4) revisão humana das direções propostas dos atos e das autodeclarações.
