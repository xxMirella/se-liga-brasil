# Catálogo de atribuições dos cargos

O serviço `service.office_duties` oferece uma síntese verificável das competências institucionais. É independente de crawler, banco e frontend: não gera requisições nem grava registros por pessoa.

A versão `2026-10-18.1` foi revisada em 18/10/2026. A data de revisão **não é vigência jurídica**. `legal_valid_from` e `legal_valid_through` permanecem nulos: os textos compilados consultados não constituem um levantamento das redações anteriores nem de todas as alterações normativas.

## Contrato

`get_office_duties(office_kind, jurisdiction, *, as_of: date)` retorna um dicionário serializável com cargo, jurisdição, data consultada, versão, data de revisão, status, itens e limites. Cada item contém `code`, `title`, `description`, `scope` e fontes com título, URL oficial e referência.

As chaves disponíveis são `federal_deputy/BR`, `senator/BR`, `state_deputy/SP`, `state_deputy/RJ` e `councillor/BR`. A jurisdição de deputados federais e senadores é nacional; a UF representada não altera esse escopo. Vereadores recebem apenas a base constitucional nacional quando `BR` é solicitado explicitamente; não há fallback automático de um município para uma legislação local diferente.

`reviewed_summary` identifica a síntese na data revisada. Datas anteriores devolvem `historical_not_verified`; posteriores devolvem `review_required`; ambos devolvem itens vazios. Cargos ou jurisdições não cobertos devolvem `not_cataloged`. A aplicação deve mostrar o estado de cobertura, sem preencher silenciosamente atribuições históricas com a redação atual. Para ampliar a validade temporal, é preciso verificar e registrar as redações aplicáveis e seus intervalos, preservando a versão anterior.

## Conteúdo e fontes

- Deputado federal: legislação, fiscalização do Executivo e deliberação orçamentária, com referências aos arts. 48, 49, X, 50, 61, 70 e 166 da [Constituição Federal compilada](https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm).
- Senador: as funções federais e apreciação de autoridades/operações financeiras nos casos do art. 52, III a IX da mesma Constituição. A competência depende do caso e da deliberação da Casa.
- Deputado estadual de São Paulo: legislação e fiscalização estaduais, conforme os arts. 19, 20, 24 e 32 da [Constituição estadual compilada](https://www.al.sp.gov.br/repositorio/legislacao/constituicao/1989/compilacao-constituicao-0-05.10.1989.html), também apresentados na página oficial de [atribuições da ALESP](https://www.al.sp.gov.br/deputados/trabalho-deputado/atribuicoes/).
- Deputado estadual do Rio de Janeiro: legislação e fiscalização estaduais, conforme a [explicação institucional da ALERJ, publicada em 31/07/2026](https://www.alerj.rj.gov.br/Visualizar/Noticia/86976). Trata-se de síntese institucional, não de inventário jurídico exaustivo.
- Vereador: legislação de interesse local e controle externo municipal nos arts. 29, 30 e 31 da Constituição Federal. A lei orgânica e o regimento de cada município ainda precisam ser catalogados.

As descrições são paráfrases curtas, sem reprodução integral das fontes. As competências são coletivas da instituição: não equivalem a metas individuais de quantidade de leis, não garantem aprovação de propostas e não permitem tratar ausência de registros como descumprimento. Autoria, relatoria, voto individual e aprovação coletiva devem continuar separados na linha do tempo.

## Extensão e custo

O índice usa a chave composta cargo/jurisdição; busca média O(1), serialização O(k) para os k itens. O catálogo é carregado uma vez; não existe N+1 de rede ou banco. Ampliações devem preservar descrição, fonte, revisão e limites, verificar normas locais e separar eventual obrigação individual de competência institucional.

Doze testes cobrem escopo, jurisdição, datas, fontes e isolamento da resposta. Não houve mudança em arquivos originais, migrações ou dados de produção.

## Catálogo persistido de competências e limites

A migração `0020_office_legal_scope_versions.sql` adiciona a tabela privada `se_liga_brasil.office_legal_scope_version`. O catálogo persistido `2026-10-18.2` é separado do snapshot inicial descrito acima: inclui competências **e** restrições, fontes por item, natureza individual ou coletiva, situação de cobertura e limites documentais. A API de leitura persistida é `database.office_legal_scopes.fetch_public_office_scopes(connection, person_id, as_of)`.

O inventário da base, consultado sem dados pessoais em 18/10/2026, apresentou três tipos em `office_term`: deputado federal (3 mandatos), senador (1) e deputado estadual (236), todos de SP. Nas candidaturas de SP/RJ há também governador, vice-governador, prefeito, vice-prefeito, vereador e suplentes de senador. A classificação das candidaturas é usada somente para mostrar o escopo do cargo disputado; candidatura ou suplência **não comprova exercício**, nem cargo atual.

Foram preparados 14 escopos, cobrindo os sete tipos aceitos no schema de mandatos e os cargos adicionais observados nas candidaturas:

- Deputado federal e senador em BR; deputado estadual em SP e RJ.
- Governador e vice-governador em SP e RJ.
- Vereador, prefeito e vice-prefeito com base nacional BR, sem presumir competência de um município específico.
- Suplente de senador em BR; deputado distrital em DF; categoria `other` em BR.

Os 14 escopos contêm 19 competências e 21 limites, com cinco URLs oficiais distintas. Nove escopos são `reviewed_baseline`, quatro são `local_law_required` e um é `unclassified`. Esses estados **não significam levantamento exaustivo** dos limites de cada cargo. Prefeito e vice-prefeito ainda têm competências locais vazias; a base disponível não identifica o município com segurança para aplicar sua lei orgânica. Deputado distrital exige revisão da Lei Orgânica do DF. `other` exige classificação antes de atribuir qualquer regra.

As competências executivas de SP usam os arts. 38 e 47 da Constituição estadual. As do RJ usam os textos oficiais da ALERJ: [governador e vice-governador, art. 140](https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=73&url=L2NvbnN0ZXN0Lm5zZi8xMTcxYzViYzU1Y2M4NjFiMDMyNTY4ZjUwMDcwY2ZiNi8xZWZkNjc4MzlmN2NjYjA0MDMyNTY2N2EwMDYzNzMxMD9PcGVuRG9jdW1lbnQ%3D) e [atribuições do governador, art. 145](https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=2&url=L2NvbnN0ZXN0Lm5zZi8xMTcxYzViYzU1Y2M4NjFiMDMyNTY4ZjUwMDcwY2ZiNi8xNzdhOWIyN2Y0NzY4NTM5MDMyNTY2N2EwMDYzNzMxMT9PcGVuRG9jdW1lbnQ%3D). A seção do art. 145 já incorpora a EC 92/2022; o PDF da biblioteca atualizado somente até 2017 não foi usado para afirmar a redação vigente.

Os limites registrados incluem separação de Poderes, reserva de iniciativa, competências territoriais, incompatibilidades parlamentares, princípios administrativos e necessidade de posse/exercício de suplente. Incompatibilidades não equivalem a proibição geral de renda privada e não produzem avaliação individual automática. Nenhum intervalo de vigência jurídica foi inventado: campos de início/fim permanecem nulos, e a resposta informa `legal_validity_not_established`. A leitura mostra o último documento revisado até a data consultada; não afirma que essa revisão iniciou vigência normativa.

A chave é cargo/jurisdição/versão. `ingest_office_legal_scopes` insere lotes sem atualizar conteúdo anterior: replay idêntico não insere linhas; conteúdo diferente na mesma chave gera erro e rollback da transação. Mudança legítima exige nova versão. Hash SHA-256 cobre o conteúdo completo. O batch executa duas consultas, sem N+1; a leitura de todos os cargos observados de uma pessoa usa uma consulta com índices existentes de pessoa e PK do catálogo. O schema tem RLS habilitada e nenhum grant para `PUBLIC`, `anon` ou `authenticated`.

Quatro testes unitários adicionais verificam cobertura de tipos, fontes por regra, lacunas e conflito de conteúdo. Dois testes SQL usam schema temporário e rollback, verificando idempotência, conflito, RLS e leitura temporal sem inferência de exercício atual.
