# Partidos: discurso e autodeclaração (camada mais fraca do modelo)

Camada de DISCURSO do modelo de classificação em que o comportamento pesa mais. Aqui só se registra o que o partido diz sobre si, com trecho e localizador. Nenhuma conclusão sobre o lado político é tirada neste documento, e as dimensões econômica e sociocultural estão `rubric_pending` (não existia `data/political-orientation/party-model/rubric.json` na execução).

## Metodologia

- Script: `scripts/archive_party_discourse.py` (`fetch`, `ingest-manual`, `build`). Requisições com User-Agent identificável e intervalo de 1,5 s. Sem disfarce, sem proxy, sem navegador automatizado.
- Bytes originais em `data/political-orientation/party-model/discourse/raw/<partido>/`; `manifest.json` com url, partido, tipo, data do documento, baixado_em, sha256, arquivo, status e motivo.
- Um `parties/<partido>/party-discourse.json` por partido com documento obtido: candidatos a rótulo declarado, até 3 trechos literais por tema (economia/Estado, trabalho, previdência, tributação, educação, saúde, segurança, meio ambiente, costumes/valores, política externa), versões do estatuto, documentos indisponíveis e limites.
- Os trechos são correspondências por palavra-chave. Não são interpretação e exigem leitura humana. O localizador é a página (PDF) ou "página HTML" mais o último "Art." anterior ao trecho. Em HTML não há paginação.
- A data do documento só é preenchida quando consta no nome ou na URL. Datas de upload na URL ficam marcadas como tal.
- URLs de origem: as fontes dos catálogos do projeto (`political_party_documentary_catalog.json`). Não foram inventadas URLs para os demais partidos.

## Bloqueio do TSE

A lista oficial e os estatutos/programas do TSE respondem 403 (Akamai) a acesso automatizado. A lista atual de partidos registrados NÃO foi confirmada; a relação abaixo vem dos catálogos do projeto e do conhecimento do agente, e deve ser conferida em https://www.tse.jus.br/partidos/partidos-registrados-no-tse. Estatutos e programas protocolados no TSE, que são a fonte primária de estatuto, ficam para download manual (ver abaixo).

## Cobertura (28/10/2026)

Obtidos documentos de 20 partidos, com 22 arquivos. Parte são páginas "sobre o partido" e não programas formais.

| Partido | Documento obtido | Observação |
|---|---|---|
| AVANTE | estatuto (PDF, upload 2023-04, texto de 2022) + página institucional | ok |
| CIDADANIA | programa (HTML, site rede23.org) | ok |
| DC | programa (HTML) | ok |
| MDB | 2 páginas (quem somos; entrevista sobre o novo programa) | não é o programa formal |
| NOVO | página de autodescrição (HTML) | não é estatuto nem programa |
| PCdoB | programa (HTML) | ok |
| PDT | estatuto (PDF, alterado em 18/03/2019) | PDF escaneado sem texto: precisa de OCR (nada extraído) |
| PL | programa (PDF, upload 2022-06) | ok |
| PODE | estatuto (PDF, versão nova do site) | a URL do estatuto de 2023/24 e a cartilha de 2021 retornam 410 |
| PP | programa (HTML) | ok |
| PRD | estatuto (PDF, 2024-05) + página | PDF escaneado, sem texto; a página não rendeu texto (JavaScript) |
| PSB | manifesto e programa (PDF, upload 2022-07) | ok |
| PSD | página de princípios e valores | não é estatuto |
| PSDB | programa (HTML) | sem candidatos a rótulo na extração; conferir leitura manual |
| PSOL | programa (HTML) | ok |
| PT | manifesto (HTML) | não é estatuto nem programa de partido completo |
| REDE | estatuto (HTML) | ok |
| REPUBLICANOS | manifesto e programa (HTML) | ok |
| SOLIDARIEDADE | página "nossa história" | não é estatuto |
| UNIÃO | manifesto (PDF, upload 2024-08) | ok |

## Lacunas (`unavailable`)

| Partido | Motivo |
|---|---|
| Lista oficial TSE (todos) | TSE bloqueia acesso automatizado (HTTP 403) |
| MISSÃO | estatuto (TSE, 04/11/2025) bloqueado, mesmo motivo |
| PV | site sem resposta (timeout) na tentativa |
| PODE | URLs antigas do estatuto e da cartilha retornam HTTP 410 (a versão nova foi obtida) |
| AGIR, MOBILIZA (ex-PMN), PCB, PCO, PMB, PRTB, PSTU, UP | sem URL verificada nos catálogos; não tentados. Candidatos ao download manual |
| PT, PSD, NOVO, MDB, SOLIDARIEDADE | só há texto institucional; falta o estatuto/programa formal (TSE) |
| Todos | histórico de estatutos, siglas anteriores, fusões e incorporações com data: NÃO extraído. Exige fontes documentais (TSE, CPDOC, Wikisource), ainda não coletadas. Os históricos relevantes dos catálogos (PTB, PSL, DEM, PR, PRB, PROS, PPS, PHS, PSC, PRP, PTC, PATRIOTA e outros) não foram baixados |
| Manifestos de campanha, Divulgacand | não pesquisados nesta rodada |

## Achados (autodeclaração, sem concluir)

- Rótulos literais encontrados nos documentos: NOVO usa "direita" ("valores da direita"); PSOL fala em "esquerda brasileira" e "estratégia socialista"; PL, PT, PCdoB, PSB e DC têm candidatos a rótulo (liberal, capitalismo/socialização, socialismo, humanismo e outros) que precisam de leitura humana.
- O MDB, em página oficial, descreve-se como de posição de centro-direita na economia e centro-esquerda na área social (título da notícia citada no catálogo). Não foi lido o programa formal.
- Em vários partidos (UNIÃO, REDE, PRD, AVANTE, PSDB) a extração não achou rótulo espacial literal. Isso não implica centro.
- Contraste com práticas aparentes não foi feito aqui; é tarefa das outras camadas.

## Download manual a partir do TSE

A pasta `data/political-orientation/party-model/discourse/manual/` tem `CHECKLIST.json` com todos os partidos (estatuto e programa) e o nome sugerido. As URLs individuais dos PDFs no TSE não foram confirmadas; navegue pela lista em https://www.tse.jus.br/partidos/partidos-registrados-no-tse. Salve cada arquivo como `SIGLA__estatuto__AAAA-MM-DD.pdf` ou `SIGLA__programa__AAAA-MM-DD.pdf` (siglas como no checklist) e rode:

```
python3 scripts/archive_party_discourse.py ingest-manual
```

O script calcula o sha256, atualiza o `manifest.json` e reconstrói os `party-discourse.json`. PDFs escaneados (PDT, PRD e outros, ver a seção "OCR de PDFs escaneados") passam por `scripts/ocr_party_discourse.py` e `scripts/ocr_pending_party_documents.py`.

## Estatutos baixados do TSE e da Justiça Eleitoral (rodada de 29/10/2026, via Chrome da usuária)

- **Escopo:** as páginas oficiais de cada partido em `partidos-registrados-no-tse` listam estatutos vigentes (hospedados em `www.tse.jus.br`) e antigos (em `www.justicaeleitoral.jus.br`). Foram baixados todos os links de estatuto: 55 do TSE (+4 de MISSAO e PRD, que uma primeira varredura não pegou) e 143 da Justiça Eleitoral, depois de remover duplicados por sha256.
- **Resultado:** **190 PDFs únicos, ~1,6 GB, 30 de 30 partidos** em `discourse/manual/`, todos com status `obtained` no `manifest.json` (ingeridos por `ingest-manual`). Nenhuma resposta HTML escapou para a pasta (1 de 1 KB foi descartada em `manual/_descartados/`).
- **Nomes:** `SIGLA__estatuto__sem-data__<nome original>.pdf`. O tipo `estatuto` inclui alterações estatutárias e folhas de rosto. A data do ato está no nome original; ela não foi normalizada.
- **Registro:** `discourse/manual_download_log_tse.json` tem nome, tamanho, sha256 e origem por arquivo, além dos descartados e duplicados. A URL exata de cada PDF antigo não foi guardada (só o domínio de origem).
- **Por partido:** PP 18, PSDB 11, AGIR 10, DC 10, PCdoB 10, PL 10, CIDADANIA 9, PV 9, MDB 8, DEMOCRATA 7, MOBILIZA 7, PT 7, REPUBLICANOS 7, AVANTE 6, NOVO 6, PODE 6, PSD 6, PSTU 6, PDT 5, SOLIDARIEDADE 5, PCB 4, PSB 4, REDE 4, PRTB 3, PSOL 3, MISSAO 2, PRD 2, UNIAO 2, UP 2, PCO 1.
- **Sites próprios (PSB, NOVO, REDE):** NOVO: o estatuto de 2026 em novo.org.br é idêntico (sha256) a um já baixado do TSE. PSB: o "Manifesto e Programa do PSB" (psb40.org.br, hospedado em autorreformapsb.com.br, 12 MB) e REDE: estatuto 2020 e página do manifesto (redesustentabilidade.org.br) foram localizados, mas o Chrome bloqueou o salvamento. Programas e manifestos desses partidos seguem **pendentes**, assim como a apresentação institucional do NOVO (2025).
- **Programas partidários:** nenhum programa partidário do TSE foi baixado; as páginas do TSE só têm estatutos.
- **OCR:** PDFs escaneados (PDT, PRD e outros) precisam de OCR. O OCR em lote é feito por outro agente; esta rodada não leu nem extraiu texto dos novos PDFs.
- O `CHECKLIST.json` é regerado pelo script a cada execução e não marca o que foi obtido; a fonte de verdade é o `manifest.json`. O `save_manifest` do script passou a gravar de forma atômica (arquivo temporário + rename).

## Limites

Discurso não comprova comportamento. Extração por palavra-chave. Os trechos não foram revisados um a um. A lista de partidos registrados não foi confirmada.
