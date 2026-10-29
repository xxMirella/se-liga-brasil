# Câmara dos Deputados: composição e orientação, 2020–2026

Implementação local em 29/10/2026. As sete projeções foram ativadas no banco utilizado pelo servidor local autorizado em `http://127.0.0.1:8787`, com backup e transação. Não houve implantação remota. A auditoria posterior de 2010–2026 corrigiu também o recorte de 2024 por UF; detalhes em `camara-conciliacao-2010-2026.md`.

## Fotografias e resultados

- 31/12/2020: 512 em exercício e uma vaga documentada; esquerda 130, centro 5, direita 296, sem classificação 81. Referência classificatória: 2018.
- 31/12/2021: 513 em exercício; esquerda 124, centro 5, direita 303, sem classificação 81. Referência: 2018.
- 31/12/2022: 513 em exercício; esquerda 120, centro 0, direita 393, sem classificação 0. Referência: 2022.
- 31/12/2023: 513 em exercício; esquerda 127, centro 0, direita 386, sem classificação 0. Referência: 2022.
- 31/12/2024: 513 em exercício; esquerda 126, centro 0, direita 381, sem classificação 5, sem filiação 1. Referência: 2022.
- 31/12/2025: 513 em exercício; esquerda 127, centro 0, direita 381, sem classificação 5. Referência: 2022.
- 29/10/2026: 513 em exercício; esquerda 125, centro 0, direita 384, sem classificação 4. Referência: 2022.

Em todos esses recortes, a direita supera o limiar institucional de 257/513 pela política editorial adotada. Isto descreve a posição estimada dos partidos: não demonstra base do governo, voto, presença ou ideologia individual. Zero de centro é resultado desta classificação e destes limiares, não preenchimento de ausências.

## Fontes e cadeia de evidência

O universo já coletado reúne 2.323 identificadores descobertos nas listagens oficiais das legislaturas 51–57. Todos os 2.323 históricos foram relidos e comparados às respostas brutas, com SHA256, preservando os registros originais em `data/enrichment`. Não foi feita uma projeção retrospectiva a partir apenas dos deputados atuais.

A composição atual foi coletada em seis páginas de `/api/v2/deputados`, com paginação completa, 513 identificadores distintos, legislatura 57 e data comum em Belém de 29/10/2026. As respostas, datas e hashes estão em `data/camara-orientation-2020-2026/sources.json`. A listagem oficial é usada como fotografia atual; a filiação de cada fotografia histórica vem dos eventos datados de seu próprio histórico.

Fontes oficiais:

- API e documentação: https://dadosabertos.camara.leg.br/swagger/api.html
- Histórico: `https://dadosabertos.camara.leg.br/api/v2/deputados/{id}/historico`
- Datas da legislatura: `https://dadosabertos.camara.leg.br/api/v2/legislaturas/{id}`
- Identidade PODE/Podemos: https://dadosabertos.camara.leg.br/api/v2/partidos/36896
- Períodos legados: `https://www.camara.leg.br/SitCamaraWS/Deputados.asmx/ObterDetalhesDeputado?ideCadastro={id}&numLegislatura=56`
- Capacidade institucional: https://www2.camara.leg.br/transparencia/acesso-a-informacao/copy_of_perguntas-frequentes/deputados
- Confirmação oficial de 513 vagas em 2026: https://www.camara.leg.br/noticias/1298957-eleicoes-deste-ano-vao-definir-54-vagas-no-senado-e-todas-as-513-vagas-da-camara

Os manifestos individuais identificam as respostas de origem; o manifesto agregado identifica o universo e seus históricos. Identidades não conciliadas ao cadastro canônico continuam `camara:{id}`; não foram criadas pessoas canônicas por aproximação nominal.

## Reconciliações de exercício

Em 2023, cinco pessoas eram excluídas por eventos simultâneos de convocação e entrada por reassunção: Coronel Telhada (222142), Darci de Matos (116379), Josias Gomes (74141), Charles Fernandes (205476) e Rodrigo Estacho (223128). A correção só resolve uma convocação administrativa quando há entrada explícita no mesmo instante, com mesmo partido e UF e sem situação de saída concorrente. Convocação isolada, conflitos de filiação e licenças permanecem sem exercício comprovado.

Em 2020, dois registros REST combinam “Entrada - Reassunção” e convocação, mas mantêm a situação `CONVOCADO`. Os períodos legados oficiais corroboram exercício de Joseildo Ramos (209189) entre 30/10/2019 e 31/01/2023, e de Paulo Magalhães (74574) entre 28/11/2019 e 29/01/2021. Foram somados apenas quando ausentes, por identificador único. A filiação veio do evento REST datado; o normalizador não lê `partidoAtual` do XML.

A vaga restante em 31/12/2020 corresponde à renúncia de Sergio Vidigal (178874), registrada em 31/12/2020 às 00:00. Neucimar Fraga (74165) tomou posse em 01/01/2021 às 17:36. Assim, a fotografia de encerramento tem 512 pessoas em exercício e uma vaga, mantendo denominador institucional 513. Essa conciliação exige os dois eventos e não infere saída por ausência em listagem.

## Política classificatória específica da Câmara

Versão `camara_2020_2026.v1`, restrita à Câmara nacional com capacidade explicitamente confirmada e marcador de versão na projeção validada. Partições antigas não recebem a aplicação editorial automaticamente. O catálogo original não foi alterado, e a regra editorial do Senado não foi transferida.

Fonte principal: Bolognesi, Codato, Ribeiro e Silva, base de classificação de partidos brasileiros 2018–2022, Harvard Dataverse, https://doi.org/10.7910/DVN/MFIXKW. Texto primário: https://periodicos.sbu.unicamp.br/ojs/index.php/op/article/view/8682072.

A regra do projeto continua: esquerda abaixo de 4,5; centro entre 4,5 e 5,5 inclusive; direita acima de 5,5, na escala de 0 a 10. Aplica-se editorialmente a onda de 2018 a 2020–2021 e a de 2022 a 2023–2026. O próprio ano de 2022 usa a observação datada. Não há interpolação de escores nem afirmação de medição acadêmica nos demais anos.

PODE e PODEMOS são a mesma organização, confirmada no registro oficial. Nos demais casos, exige-se correspondência de sigla com a onda: PRD não herda PTB/Patriota; MISSÃO não tem observação no catálogo; PL, Republicanos e Cidadania não herdam automaticamente as siglas anteriores na aplicação de 2018. A expressão oficial `S.PART.` é preservada nos dados e apresentada como sem filiação, separadamente de sem classificação.

Foi pesquisada também a fonte primária Zucco e Power, *The ideology of Brazilian parties and presidents*, https://ora.ox.ac.uk/objects/uuid%3Abbf2faf9-5a2e-47c2-a7ef-c0b8acdf9a0e. Sua população respondente, escala e ondas diferem do survey de especialistas. Não foram misturados escores ou criadas observações de 2020/2026 a partir dela.

A sensibilidade aplica as duas ondas separadamente às mesmas bancadas históricas, preservando organizações ausentes como sem classificação. Em 2026, por exemplo, a onda 2018 resulta em direita 191, esquerda 116, centro 9 e sem classificação 197; não comprova maioria nessa alternativa. Isto decorre também da cobertura de organizações e mudanças de sigla; não demonstra evolução ideológica individual. A conclusão de maioria é condicionada ao método explicitado na interface.

## Integração, validação e custo

O cartão da Câmara reutiliza o semicírculo e as barras existentes. Acrescenta fotografia, distribuição, contagens por partido, classificação ausente, vagas, cobertura e sensibilidade. A linha do tempo usa a mesma regra de maioria e mantém o denominador de 513 mesmo com lacunas. Eventos datados de entrada, saída e alteração partidária são deduplicados e exibidos por dia, com aviso de que não constituem pessoas distintas ou uma composição simultânea. Em 2026, os históricos individuais têm coletas de 23 a 26/10, enquanto a fotografia atual é de 29/10; não se promete atualização intranual posterior à coleta de cada histórico.

As sete projeções locais e seus hashes estão em `data/camara-orientation-2020-2026/annual-manifest.json`; resultados em `audit.json`. Nenhuma partição supera o orçamento existente de 256 KiB.

Validação: 136 testes relevantes passaram; nove testes condicionados a ambiente de integração foram pulados. Além deles, as sete projeções reais foram ativadas e lidas em uma transação com rollback, com verificação de atualização do histórico, idempotência, renderização do painel e preservação das versões públicas após rollback. Ruff passou e o revisor estrutural do projeto retornou zero achados; também foram revisadas as regras temporais e de maioria.

Reconstruir custa O(Y × E), com Y=7 fotografias e E eventos históricos; memória O(E + M), com M integrantes e projeções. As consultas de identidade e de composição são em lotes; não há consulta remota por partido na requisição pública. O agrupamento por orientação custa O(P), com P bancadas, e o índice do catálogo permite busca média O(1). As requisições públicas continuam a usar as projeções anuais e o histórico reduzido/versionado, sem reler os arquivos de origem.

## Reprodução e ativação separada

Coleta em diretório novo:

```sh
PYTHONPATH=src .venv/bin/python scripts/collect_chamber_orientation_sources.py --storage data/chamber-capture-YYYYMMDD
```

Reconstrução local, sem publicar:

```sh
PYTHONPATH=src .venv/bin/python scripts/build_chamber_orientation_annual.py --env-file /caminho/seguro/.env
```

O parâmetro `--apply` ativa as sete projeções nacionais e atualiza o histórico versionado em uma transação, preservando um backup dos registros anteriores. Foi executado no banco local autorizado. Os estados e outras instituições permanecem fora do escopo da ativação desta integração nacional.


## Auditoria posterior por UF em 29/10/2026

A conciliação nacional anterior ocultava em 2024 um excesso no Acre (9/8) e uma diferença no Paraná (29/30). Zé Adriano (230768) tinha atualização de perfil de 31/12/2024 explicitamente anterior à posse, ocorrida em 01/01/2025. Rodrigo Estacho (223128) tinha reassunção em 04/12/2024 sob código `CONVOCADO`, corroborada pelo período legado oficial até 13/11/2025. A correção retira o primeiro do recorte de 2024 e inclui o segundo, preservando os outros 512 integrantes: AC 8/8 e PR 30/30. PP perde uma cadeira e PSD ganha uma; as contagens por orientação acima permanecem iguais.

O seletor agora exclui atualizações explicitamente anteriores à posse, e o construtor verifica a capacidade de todas as UFs. Períodos legados com fim vazio só sustentam exercício até a data da aquisição. Os contadores intranuais passaram a exigir `Exercício` para entradas; convocação administrativa não entra nessa contagem. O recorte ES/2020 e as cinco conciliações de 2023 foram preservados.

As evidências novas e a prova de preservação dos demais integrantes estão em `data/camara-reconciliation-2010-2026/recent-2024-reconciliation.json`; os XMLs oficiais e seus hashes também foram preservados. A política `camara_2010_2019.v2` é específica da integração histórica e não altera a política classificatória de 2020–2026. A validação final passou 148 testes, inclusive integração SQL isolada, Ruff e revisão estrutural sem achados. Os 17 recortes de 2010–2026 foram verificados por HTTP no servidor local.
