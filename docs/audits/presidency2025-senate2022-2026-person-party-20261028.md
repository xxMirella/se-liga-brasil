# Presidência de 2025, Senado de 2022–2026 e vínculos pessoa–partido

Referência: **28/10/2026**. Auditoria dos arquivos, banco real, API e HTML locais. Sem deploy ou alteração de layout.

## Resultado

Lula/PT está corretamente identificado na Presidência de 2025. A orientação **Esquerda** é uma síntese editorial do governo, explicitamente separada da filiação partidária. As fotografias anuais do Senado somam 81 cadeiras; isso **não certifica cobertura diária completa**.

Foram corrigidos três vínculos atuais do Podemos que estavam ausentes no banco. O histórico parlamentar de Flávio Bolsonaro em 2019–2021 foi salvo no UUID confirmado pelo identificador oficial do Senado e consultado cronologicamente no banco.

## Presidência de 2025

O titular é Luiz Inácio Lula da Silva, em exercício desde 01/01/2023. A linha do tempo recorta 01/01/2025–01/01/2026, com fim exclusivo. A [biografia oficial da Câmara, ID 139289](https://www.camara.leg.br/deputados/139289/biografia), consultada novamente nesta auditoria, identifica a Presidência pelo PT desde 2023. A fonte de exercício é a biografia 204 do Arquivo Nacional, arquivada em 23/10/2026. A atribuição do partido do mandato não é uma certidão diária de filiação civil.

A orientação tem status `editorial_mandate_summary`. O estudo acadêmico citado foi publicado em 2023 e analisa o início do terceiro governo: **não é uma medição acadêmica anual de 2025**. A API e a renderização preservam essa ressalva e retornam Esquerda. Algumas páginas oficiais da Presidência/EBC sobre 2025 estão temporariamente indisponíveis por legislação eleitoral; a indisponibilidade não foi interpretada como ausência de exercício.

A projeção ainda usa `person_id=arquivo-nacional-president:204`, um ID da fonte, e não o UUID da tabela `person`. Não foi encontrado um registro Lula no inventário consultado de pessoas/identificadores. A importação relacional presidencial e sua ponte canônica seguem pendentes; nenhuma identidade foi criada por nome.

A cobertura é `observed_partial`. Não se afirma que esta auditoria reconstruiu todas as substituições temporárias pelo vice-presidente ou outros substitutos constitucionais.

## Senado, ano a ano

- **2022:** fotografia nominal de 31/12 com 81 pessoas; 27 UFs com três pessoas cada. São 52 UUIDs canônicos e 29 IDs de fonte ainda sem ponte canônica. Partidos: PSD 14; MDB 13; PODE 8; PP, PL e PT 7 cada; UNIÃO e PSDB 6 cada; PDT 4; PTB 2; S/Partido, CIDADANIA, REPUBLICANOS, PROS, REDE, PSB e PSC 1 cada.
- **2023:** relatório oficial de 22/12 e reconstrução nominal de 31/12 somam 81, com as mesmas contagens após normalizar PODE/PODEMOS. A reconstrução contém 73 UUIDs e oito IDs de fonte. Partidos: PSD 15; PL 12; MDB 11; PT 8; PODE e UNIÃO 7 cada; PP 6; REPUBLICANOS e PSB 4 cada; PDT 3; PSDB 2; REDE e NOVO 1 cada.
- **2024:** relatório de 23/12 com PL 13 e PODEMOS 7; reconstrução de 31/12 com PL 14 e PODE 6. Ambas somam 81 e são corretas em suas respectivas datas. Rodrigo Cunha (PODE) renunciou em 29/12 e Dra. Eudócia (PL) assumiu; a [TV Senado de 30/12/2024](https://www12.senado.leg.br/tv/programas/noticias-1/2024/12/rodrigo-cunha-renuncia-e-dra-eudocia-reassume-mandato-de-senadora) confirma a sucessão. A reconstrução tem 74 UUIDs e sete IDs de fonte. Não se corrigiu uma fotografia com a data da outra.
- **2025:** relatório de 22/12 e reconstrução de 31/12 somam 81. A reconstrução tem 73 UUIDs e oito IDs de fonte. Partidos: PL 15; PSD 14; MDB 10; PT 9; PP 7; REPUBLICANOS e UNIÃO 5 cada; PODE e PSB 4 cada; PDT e PSDB 3 cada; S/Partido e NOVO 1 cada. Giordano está sem partido no fim de 2025, corretamente; não recebeu retroativamente o partido de 2026.
- **2026:** fotografia publicada em 22/10 com 81 pessoas, todas com UUID, e três pessoas por UF. A auditoria oficial existente de 28/10 confirma as contagens: PL 15; PSD 14; MDB e PT 9 cada; PP 8; PSB 7; REPUBLICANOS 6; PSDB 4; PODE e UNIÃO 3 cada; AVANTE, PDT e S/Partido 1 cada. A comparação nominal tem 80 nomes iguais após normalizar caixa/acentos e uma variação “Nelsinho Trad”/“Nelsinho Trad Filho”, na mesma UF e partido. Não foi criada associação de identidade por nome.

Os relatórios de 2023–2025 são **agregados**: `members=[]` no nível principal da API é intencional. Os 81 nomes reconstruídos em outra data estão em `dated_exercise_snapshot.members`. Não foram misturados nomes de 31/12 com contagens oficiais de 22 ou 23 de dezembro. As cinco APIs e cinco páginas HTML responderam **HTTP 200**.

A [posse dos eleitos de 2022](https://www12.senado.leg.br/institucional/presidencia/noticia/rodrigo-pacheco/rodrigo-pacheco-empossa-27-novos-senadores-eleitos-em-outubro-de-2022) ocorreu em 01/02/2023. A eleição não foi tratada como troca imediata de ocupantes em 2022; a eleição de 2026 também não antecipa a posse de 2027.

Fontes anuais: relatórios oficiais de [2023](https://www25.senado.leg.br/documents/12427/137800151/RAP+2023/07605fc0-fe63-4fe6-8901-36abbdf24390), [2024](https://www25.senado.leg.br/documents/12427/145699807/RAP+2024/a431784a-3824-4222-a933-f50338b13871) e [2025](https://www25.senado.leg.br/documents/12427/153850672/RAP+2025/d1d2df43-bd1d-4220-acf5-07dc43c93883); exercícios das legislaturas 56/57 e filiações individuais em `data/senate-history/historical-senate-evidence.json`; relatório atual em `data/political-orientation/sources/senate-current-roster-20261028.html`.

### Limites dentro de cada ano

Foram examinadas **184 datas de fronteira** de exercício ou filiação, considerando inícios e o dia posterior ao fim inclusivo da fonte. Em 56 delas, o conjunto bruto de pessoas não tem 81 integrantes: 13 em 2022, 15 em 2023, dez em 2024, quatro em 2025 e 14 em 2026. Os totais brutos variam de 79 a 85. Isso **não significa 85 cadeiras nem comprova vacâncias reais**: há sobreposições e hiatos administrativos a conciliar com os Diários, sobretudo em substituições e posses.

Em 19 fronteiras falta um intervalo de filiação de alguma pessoa: 17 em 2022, uma em 2025 e uma em 2026. Não foram encontrados dois partidos distintos simultâneos para a mesma pessoa. O JSON registra as datas e os IDs afetados. Não se preencheram lacunas com partido atual ou proximidade entre datas.

## Integridade e três correções no banco

Inventário inicial: **15.921 pessoas, 694 identificadores, 38 registros partidários e 31.089 filiações**. Não foram encontrados órfãos nas FKs de filiação (pessoa, partido ou fonte), intervalos invertidos ou um identificador oficial do Senado ligado a duas pessoas. Foram inventariadas as constraints reais. Isso verifica integridade estrutural, **não certifica a identidade semântica das 15.921 pessoas**.

As 81 observações institucionais iniciais do Senado pertenciam a 77 pessoas, pois quatro pessoas tinham duas observações. Faltavam os três vínculos PODE e a filiação partidária de Romário, que está corretamente sem partido na fonte.

A tabela preserva PODE/código 19 (ID 274) e PODE/código 20 (ID 9). A [tabela oficial do TSE](https://www.tse.jus.br/partidos/partidos-registrados-no-tse) documenta a troca de número aprovada em 05/03/2024, processo 0600672-47.2023.6.00.0000. A ingestão Senado exigia unicidade da sigla e omitira os três vínculos diante dessa ambiguidade.

Foram inseridos somente os vínculos institucionais observados em 23/10/2026, com partido ID 9 e fonte/identidade comprovadas:

- Giordano: Senado 6008; `person_id=2b12efea-eb81-4571-a176-445ac27fcbcd`; filiação 40992; fonte 263768.
- Styvenson Valentim: Senado 5959; `person_id=697bdb36-e248-4ddf-83b7-767617f35ec7`; filiação 40991; fonte 265309.
- Zequinha Marinho: Senado 3806; `person_id=fb2af9ca-0497-402e-8cda-d7cce1030c06`; filiação 40990; fonte 265819.

As datas `valid_from/valid_until` permanecem NULL nessas observações pontuais: 23/10 não foi inventado como data civil de filiação. A segunda execução inseriu zero linhas. A ingestão agora aceita PODE 20 para observações desde 05/03/2024; não apagou PODE 19 nem reescreveu dados eleitorais anteriores.

Depois do reparo: **84 observações institucionais de 80 senadores**. Todos os vínculos conferidos correspondem ao ID oficial no URL e ao partido no payload da fonte. Apenas Romário (Senado 5322) permanece sem filiação institucional partidária, coerente com Sem Partido. A projeção materializada `person_profile` foi atualizada.

### Pendências fora do recorte

Há dois pares administrativos simultâneos na Câmara envolvendo os dois IDs PODE para a mesma pessoa e observação: filiações 40125/40126 (`person_id=2bafa18c-b166-475d-a84a-97844cdc0b41`) e 40127/40128 (`person_id=337b8005-b3b5-4701-a494-6823c2096112`). Isso não prova duas filiações civis diferentes. A reconciliação do catálogo e da ingestão Câmara precisa preservar o número de cada eleição; não foi feita fusão ampla de partidos ou pessoas.

## Flávio Bolsonaro: histórico salvo e query executada

Resolução por `source.code='senado'`, `namespace='senator'`, `external_id='5894'` → **`person_id=4c30de36-97ec-4f4c-af89-dd16ff3d99a9`**. Não houve associação por nome.

A [API oficial de filiações](https://legis.senado.leg.br/dadosabertos/senador/5894/filiacoes.json) foi consultada diretamente em 28/10/2026 e arquivada. SHA256 dos bytes originais: `46ee6200ddeabd85ad7ccae63cbb3ca8033669aceeb73b759501664069298eb0`. Fonte relacional **311675**.

- PSL: 01/01/2019 até 20/11/2019, fim exclusivo; filiação 40984, partido 272.
- Sem partido registrado no Senado: 20/11/2019 até 31/05/2021, fim exclusivo; `person_fact` datado, sem criar partido fictício.
- PATRIOTA: 31/05/2021 até 30/11/2021, fim exclusivo; filiação 40985, partido 291.
- PL: desde 30/11/2021, sem fim informado; filiação 40986, partido 10.

A [modificação oficial para PL](https://www12.senado.leg.br/manualdecomunicacao/senadores/modificacoes/flavio-bolsonaro-muda-do-partido-patriota-para-o-partido-pl) e o relatório de 2021 corroboram a mudança de 30/11/2021. O histórico parlamentar não é uma certidão civil do TSE: relatos de passagem pelo Republicanos em 2020–2021 não aparecem nessa API. Portanto, S/Partido foi salvo **como situação registrada no Senado**, com essa limitação, e não como conclusão de ausência de filiação civil. A comprovação civil e suas datas seguem pendentes.

O escopo `institution:senado:historical_affiliations` separa esses períodos das observações atuais e declarações eleitorais. A segunda importação preservou os mesmos IDs e quatro intervalos na consulta. A normalização converte fim inclusivo em exclusivo e valida ID oficial, intervalos e partidos existentes antes de gravar. Retorno ao mesmo partido é recusado explicitamente até haver fonte por intervalo compatível com a constraint atual; nenhum intervalo é descartado silenciosamente.

Consulta pronta: **`db/queries/senator_affiliation_history_5894.sql`**. Resolve o UUID pelo ID oficial, usa o snapshot histórico mais recente, faz JOIN das filiações e UNION dos períodos Sem Partido, retornando pessoa, partido, datas, IDs e URL/hash da fonte em ordem cronológica. Resultado executado: `data/political-dashboard/flavio-affiliation-history-2019-2021-verified-20261028.json`.

## Validação técnica e artefatos

Os três novos testes cobrem a sequência real de Flávio, fins exclusivos, ID oficial incorreto e rejeição de sobreposição. Ruff passou nos quatro arquivos Python novos. A revisão estrutural não encontrou achados nos arquivos desta entrega. Ordenar N intervalos custa O(N log N), com memória O(N); leitura e gravação dos vínculos são feitas em lote, sem N+1 por intervalo. A operação real foi validada sem dados fictícios.

Artefatos principais:

- `data/political-dashboard/presidency2025-senate2022-2026-validation-20261028.json`: fotografias, API, Presidência e fronteiras temporais.
- `data/political-dashboard/person-party-integrity-20261028.json`: inventário e integridade antes/depois.
- `data/political-dashboard/pode-affiliation-repair-20261028.json`: três vínculos e idempotência.
- `db/repairs/senate_podemos_affiliation_20261028.sql`: reparo delimitado e reproduzível.
- `scripts/persist_senate_affiliation_history.py`: importação do arquivo oficial com identidade existente e transação.

Rodada final após estabilização do teste compartilhado: **70 testes aprovados**, incluindo histórico e composição do Senado, filiações e explicações presidenciais. Ruff aprovado; revisão estrutural sem achados neste escopo. Na execução global final apareceram três achados concorrentes externos: profundidade de `extract_matches` em `scripts/archive_party_discourse.py:210` e complexidade/profundidade de `aggregate_camara_year` em `scripts/collect_party_policy_projects.py:82`; o coordenador foi informado. A query SQL final foi executada novamente em leitura e retornou os quatro períodos do mesmo UUID, usando o snapshot histórico mais recente.
