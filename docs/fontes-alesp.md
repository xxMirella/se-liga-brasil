# Investigação oficial ALESP — 16/10/2026

## Coleta e limites

`manifest.json` contém URL original, caminho local, SHA-256, bytes, HTTP status, Content-Type e instante UTC de coleta de cada resposta baixada. Não foram alterados esquema ou banco. Respostas brutas preservadas. Os arquivos payroll_2026_08.html e payroll_2025_12.html são amostras dos mesmos conteúdos posteriormente baixados com nome oficial; NÃO são folhas adicionais.

O índice oficial https://www.al.sp.gov.br/alesp/folha-de-pagamento-deputados/ oferece 11 competências: outubro/2025 a agosto/2026. Não presumir disponibilidade de setembro/outubro pela data atual. Usar descoberta de links com urljoin (há links absolutos), filtragem de host e chave por competência. Histórico anterior pode existir em outras páginas ou arquivos não indexados, mas não foi confirmado.

## Contrato da folha de deputados

URL: https://www.al.sp.gov.br/repositorio/folha-de-pagamento/folha-deputados-YYYY-MM.html
HTML tabela com quatro células: Nome, Remuneração Bruta (R$), Tributos (R$), Remuneração Líquida (R$). O cabeçalho utiliza `td`, não `th`. Nomes são apresentados completos, sem CPF, matrícula ou ID parlamentar.

As notas oficiais definem bruto como subsídio já reduzido pelas ausências dedutíveis (faltas injustificadas e licenças pessoais); tributos agregam IR e contribuição previdenciária, com possível variação pelo órgão de origem; líquido é bruto menos tributos. Não são quatro tipos de despesa e não se deve somar bruto com líquido. Ausências não têm coluna de valor, e a nota não individualiza a causa de um bruto reduzido.

As 11 folhas contêm 1.039 linhas pessoais. Dezembro/2025 contém 98 pessoas, maio/2026 contém 95, demais competências 94. Todas satisfazem bruto - tributos = líquido em Decimal exato, nenhuma tem nome duplicado dentro da competência. Dezembro possui valor bruto e líquido negativos (-4.636,61) e valor zero; são dados oficiais válidos a preservar. Não inferir ajuste, estorno ou afastamento sem evidência complementar. Não impor CHECK amount >= 0. `payroll_summary.json` documenta métricas por competência.

Março/2026 é Latin-1, os demais arquivos de folha analisados são UTF-8; o índice e páginas de catálogo também exigem cuidado com encoding. Preservar bytes e resolver charset por metadados/decode estrito com fallback explícito. Converter BRL com Decimal ou centavos inteiros, nunca float.

As folhas não fornecem data efetiva de pagamento, rubricas, base legal versionada, 13º destacado, férias destacadas ou identificação de folha complementar. Não gerar campos inferidos com valores zero: desconhecido deve permanecer nulo. O texto legal de rodapé é o mesmo nas amostras e cita Lei 17.617/2023; não tratar como verificação completa da vigência normativa.

## Identidade e partido

https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml contém 94 deputados e campos: IdDeputado, IdSPL, IdUA, Matricula, NomeParlamentar, Partido, Situacao, Aniversario, Biografia, Email, HomePage, telefone e localização do gabinete. Aniversario é apenas DD/MM. Não há nome civil estruturado, CPF, nascimento completo ou identificador TSE. `NomeParlamentar` pode divergir do nome civil da folha. Não associar automaticamente à pessoa TSE por nome sozinho.

Guardar sujeito local da fonte e pagamento mesmo sem person_id resolvido. A ligação definitiva deve usar ponte verificada (ID ALESP + identidade TSE/documento/nascimento ou outra evidência documental), com método, evidências, status e instante de resolução. Nome + aniversário + eleição/UF/cargo são evidências para candidatos, não garantia documental de identidade. Ambiguidades ficam em revisão.

https://www.al.sp.gov.br/repositorioDados/deputados/partidos.xml fornece Nome, Numero e Sigla. Inclui Sem Partido com sigla SP e número 00: nunca confundir sigla partidária SP com UF. XML deputados registra partido observado atual, sem ingresso/saída. Não produz datas efetivas de filiação SCD2. Guardar observed_at e fonte, não declarar entrada na data de coleta.

O catálogo anuncia /api/deputado/{partido}, /api/deputadoPresenca/{deputado}, /api/despesa/{ano}/{mes}, /api/propositura. Requests reais /api/deputado e /api/deputado/PL retornaram HTTP 404; esses contratos estão anunciados, porém não operacionais nesses caminhos. Priorizar XML/HTML confirmados.

## Modelagem proposta

- payroll_statement / public_office_remuneration: órgão pagador, tipo de população (deputado), competência DATE no primeiro dia do mês, identificador do sujeito na fonte, nome publicado, person_id nullable, cargo, moeda BRL, bruto, tributos e líquido NUMERIC(18,2), tipo de folha unknown/regular conforme fonte comprovada, data de pagamento nullable, source_record_id, source_document_id, row_locator, observed_at.
- Identidade idempotente provisória da folha: ALESP + deputies_payroll + competência + nome normalizado; rejeitar/quarentenar duplicatas dessa chave antes de projetar. Hash do conteúdo versiona correções; não usar hash monetário como identidade do fato, pois republicação corrigida deve substituir versão e preservar anterior.
- Nome não é chave global de pessoa. Criar subject_key local e resolver person_id por serviço de identidade; manter rastreabilidade do vínculo.
- Histórico de republicação: valid_from/valid_until do sistema, payload_hash e referência à evidência bruta. Mudanças de valor não são novo mês. Uma nova coleta do mesmo conteúdo não cria versão nova. Transação + unique parcial protege concorrência.
- Não colocar salário como atributo permanente em person: projeção do perfil pode selecionar último pagamento conhecido e exibir competência/órgão. Pagamento em agosto não prova exercício atual em outubro; folha ausente não prova saída.

## Demais dados no catálogo oficial

Portal https://www.al.sp.gov.br/dados-abertos/ anuncia 26 conjuntos, 29 recursos e migração futura para https://ckan.al.sp.gov.br/alesp-dados-abertos. Não assumir CKAN operacional sem validação.

Deputados (grupo 2): deputados, partidos, despesas de gabinete. Despesas são ressarcimentos/despesas de mandato, NÃO remuneração pessoal.

Administração (grupo 21): histórico de cargos dos funcionários, histórico de lotações, lotações dos servidores, unidades administrativas. Recurso de cargos aponta https://www.al.sp.gov.br/repositorioDados/administracao/funcionarios_cargos.xml e documentação PDF; o portal informa atualização 12/05/2023 para históricos de cargos/lotações, portanto cuidado com obsolescência. São funcionários, não inferir automaticamente mandatos de deputados a partir deles.

Processo legislativo (grupo 1): autores, comissões permanentes, deliberações, membros, naturezas de documento, palavras-chave, pareceres, presenças nas comissões, proposituras, regimes de tramitação, reuniões, tramitação/andamentos, votações nas comissões. Separar votos individuais de resultados coletivos, autoria de relatoria e presença de remuneração.

Legislação (grupo 41): normas, anotações, tipos de normas, temas, subtemas. Agenda (grupo 81): eventos.

Grandes XML legislativos não foram baixados sem finalidade definida: catálogo e metadados foram preservados; folhas de deputados e XMLs de deputados/partidos foram baixados integralmente. Remuneração de servidores é outro fluxo do portal de gestão de pessoal, não incluído no contrato acima e precisa investigação independente antes de prometer cobertura.

## Verificações recomendadas para implementação

Parser: charset misto, cabeçalho td, negativo e zero em dezembro, 98/95/94 linhas conforme mês, idempotência repetida, republicação corrigida, ausência de pessoa resolvida, sujeito homônimo, isolamento de despesas de gabinete. Complexidade O(n) por folha, memória O(n) ou streaming; resolução de identidades por lote, sem N+1 banco/rede.

## Ampliação do catálogo — coleta completa dos recursos anunciados

A coleta posterior percorreu **26 conjuntos e 29 recursos** de todos os cinco grupos. Foram preservadas 55 páginas de metadados, 29 PDFs de dicionário e **28 arquivos estruturados completos** (XML ou ZIP contendo XML). O histórico completo de andamentos ultrapassou o limite de 100 MiB: `datasets/101_documento_andamento.zip.partial` contém somente prefixo binário e **não é ZIP utilizável nem cópia completa**. Nenhuma amostra desse histórico foi interpretada. O recurso de andamento atual foi baixado e interpretado integralmente.

`catalog-resources.json` é o inventário machine-readable: datasets, recursos, URLs, estado de download, arquivos, bytes/hash, esquemas e contagem real de registros. `catalog-download-manifest.json` mantém o manifesto desta coleta expandida; `manifest.json` mantém a coleta inicial. PDFs têm extração textual adjacente para consulta, não são documentos pessoais de proposições. Total recebido nesta ampliação: **365.616.697 bytes**, inclusive o prefixo interrompido. Limites: 100 MiB por transferência, 500 MiB por execução. XMLs em ZIP foram lidos diretamente sem extração em disco e dentro de teto descomprimido de 250 MiB por membro.

Todos os 28 recursos estruturados completos foram percorridos integralmente para identificar campos e contagens. Tipos de elementos XML são textuais: `field_roles` no catálogo indica papel semântico provável, não substitui validação dos tipos nos dicionários oficiais. Não foram inferidas relações de pessoa pelo nome.

### Informações úteis para os próximos módulos

- **Despesas de gabinete:** 166.938 agregados por Ano, Mes, Matricula, Tipo, CNPJ, Fornecedor e Valor. O dicionário explica reembolsos agrupados, não notas fiscais individuais nem salário. Matricula permite ponte para deputados XML; CNPJ pode conter CPF do favorecido segundo documentação. Não supor empresa em toda linha. O XML real não possui campo Deputado descrito no PDF.
- **Cargos de funcionários:** 43.302 eventos com DataInicio/DataFim, IdCargo, NomeCargo, NomeFuncionario, IdRegime/NomeRegime; **sem identificador pessoal único**. **Lotações históricas:** 64.546 vínculos com datas, IdUA e nome; também sem identificador único de funcionário. Essas datas referem-se a cargos/lotações administrativas, não filiação partidária.
- **Lotação atual:** 3.579 registros de nome/cargo/regime/unidade, sem datas e sem ID pessoal; **428 unidades administrativas** com hierarquia IdUAPai e DataInativacao.
- **Autores:** 1.119.878 relações IdDocumento/IdAutor/NomeAutor. O PDF define autores; não reclassificar como apoiadores apenas pelo resumo do grupo. Antes de juntar à pessoa, validar namespace IdAutor versus IdSPL/IdDeputado.
- **Membros de comissão:** 7.523 registros com DataInicio/DataFim, papel e efetividade; são intervalos de comissão, não partido nem mandato geral.
- **Presenças:** 28.437 vínculos com IdDeputado/IdReuniao e DataReuniao. **Votos em comissões:** 226.067 registros individuais com IdDeputado, IdDocumento, IdReuniao, IdPauta, TipoVoto e Voto; não são votos do plenário. PDF descreve códigos F/C/S/O/P/T/A/B, preservar código e rótulo.
- **Proposituras:** 278.014 documentos com natureza, número, ano, ementa e datas de entrada/publicação; autoria reside em recurso separado. **Pareceres:** 154.884 registros com relatoria especial, voto vencido, comissão, tipo e URL; sem identificação estruturada universal de relator.
- **Regimes:** 448.206 intervalos de tramitação com DataInicio/DataFim. **Andamento atual:** 260.059 documentos/eventos com etapa, descrição e data. **Reuniões:** 8.037; **deliberações:** 37.295. **Comissões:** 144 com data de encerramento quando publicada.
- **Normas:** 254.067 registros com tipo, número, data, ementa, autores textuais, situação e URL; **68.884 anotações** estabelecem relações com norma citada por tipo/número/data. **Agenda:** 60.304 eventos, com datas, horários, local e sinalizadores de cancelamento/transferência.
- **Partidos:** 25 entradas; deputados atuais: 94. Nenhum desses recursos publicou datas estruturadas de filiação/desfiliação partidária no esquema observado. Dados de partido continuam sendo observações da fonte.

Os dicionários PDFs são úteis, mas têm divergências com conteúdo real: deputados descreve Partido numérico, porém XML contém sigla; despesas descreve nome de deputado ausente no XML. Datas de atualização de catálogo não garantem que eventos internos estejam atualizados. Antes de ingestão de cada domínio, definir cobertura temporal observada, chaves da fonte, granularidade, rubricas/códigos e política de republicação.

### Inventário por recurso

- **61 — Deputados**: 61_deputados.xml: downloaded, 301097 bytes. Deputado (94 registros): IdDeputado, IdSPL, IdUA, Situacao, Andar, Aniversario, txtAreaAtuacao, txtBaseEleitoral, Biografia, Email, Matricula, NomeParlamentar, PlacaVeiculo, Sala, Partido, Telefone, HomePage

- **21 — Despesas de Gabinete**: 21_despesas_gabinetes.xml: downloaded, 40015353 bytes. despesa (166938 registros): Ano, Matricula, Mes, Valor, CNPJ, Tipo, Fornecedor

- **1 — Partidos**: 1_partidos.xml: downloaded, 2323 bytes. Partido (25 registros): Nome, Numero, Sigla

- **182 — Histórico de Cargos dos Funcionários**: 182_funcionarios_cargos.xml: downloaded, 13570058 bytes. CargoFuncionario (43302 registros): DataInicio, IdCargo, IdRegime, NomeCargo, NomeFuncionario, NomeRegime, DataFim

- **181 — Histórico de Lotações dos Servidores**: 181_funcionarios_lotacoes.xml: downloaded, 16543800 bytes. LotacaoFuncionario (64546 registros): DataFim, DataInicio, IdUA, NomeFuncionario, NomeUA

- **161 — Lotações dos Servidores**: 161_lotacoes.xml: downloaded, 974249 bytes. Lotacao (3579 registros): IdCargo, IdRegime, IdUA, NomeCargo, NomeFuncionario, NomeRegime, NomeUA

- **51 — Unidades Administrativas**: 51_uas.xml: downloaded, 97626 bytes. UA (428 registros): DataInativacao, IdSEFAZ, IdUA, IdUAPai, NomeOficialUA, NomeUA, EmailResponsavel, SiglaUA

- **81 — Autores**: 81_documento_autor.zip: downloaded, 6549351 bytes. DocumentoAutor (1119878 registros): IdAutor, IdDocumento, NomeAutor

- **43 — Comissões Permanentes**: 43_comissoes.xml: downloaded, 33600 bytes. Comissao (144 registros): DataFimComissao, IdComissao, NomeComissao, SiglaComissao, DescricaoComissao

- **52 — Deliberações nas Comissões**: 52_comissoes_permanentes_deliberacoes.xml: downloaded, 12529990 bytes. ReuniaoComissaoDeliberacao (37295 registros): Deliberacao, DataInclusao, DataSaida, IdDeliberacao, IdDocumento, IdPauta, IdReuniao, NrOrdem

- **45 — Membros de Comissões Permanentes**: 45_comissoes_membros.xml: downloaded, 2411060 bytes. MembroComissao (7523 registros): DataInicio, Efetivo, IdComissao, IdMembro, IdPapel, NomeMembro, Papel, SiglaComissao, DataFim

- **44 — Natureza do Documento**: 44_naturezasSpl.xml: downloaded, 14070 bytes. natureza (106 registros): idNatureza, nmNatureza, sgNatureza, tpNatureza

- **41 — Palavras-chave (indexação)**: 41_palavras_chave.xml: downloaded, 4553241 bytes. PalavraChave (27666 registros): IdPalavra, Palavra, PalavraSemAcento

- **42 — Palavras-chave (indexação)**: 42_documento_palavras.zip: downloaded, 5896398 bytes. DocumentoPalavra (1277181 registros): IdDocumento, IdPalavra

- **102 — Pareceres**: 102_tipo_parecer.xml: downloaded, 6092 bytes. TipoParecer (46 registros): IdTipoParcer, TipoParecer

- **103 — Pareceres**: 103_propositura_parecer.zip: downloaded, 4715386 bytes. ProposituraParecerComissao (154884 registros): AnoParecer, Descricao, Data, AdReferendum, RelatorEspecial, VotoVencido, IdComissao, IdDocumento, IdParecer, IdTipoParecer, TipoParecer, NrParecer, SiglaComissao, TpParecer, URL

- **53 — Presença nas Comissões**: 53_comissoes_permanentes_presencas.xml: downloaded, 8232760 bytes. ReuniaoComissaoPresenca (28437 registros): DataReuniao, IdComissao, IdDeputado, IdPauta, IdReuniao, Deputado, SiglaComissao

- **56 — Proposituras**: 56_proposituras.zip: downloaded, 17645543 bytes. propositura (278014 registros): AnoLegislativo, CodOriginalidade, Ementa, DtEntradaSistema, DtPublicacao, IdDocumento, IdNatureza, NroLegislativo

- **82 — Regimes de Tramitação das Proposituras**: 82_documento_regime.zip: downloaded, 1809122 bytes. DocumentoRegime (448206 registros): DataFim, DataInicio, IdDocumento, IdRegime, NomeRegime

- **54 — Reuniões de Comissão**: 54_comissoes_permanentes_reunioes.xml: downloaded, 2946545 bytes. ReuniaoComissao (8037 registros): Situacao, Data, IdComissao, IdPauta, IdReuniao, Presidente, NrConvocacao, NrLegislatura, TipoConvocacao, CodSituacao

- **101 — Tramitação**: 101_documento_andamento.zip.partial: limit_exceeded, 104857600 bytes. Esquema não inspecionado: recurso incompleto.

- **221 — Tramitação**: 221_documento_andamento_atual.zip: downloaded, 1952940 bytes. DocumentoAndamento (260059 registros): Descricao, Data, IdComissao, IdDocumento, IdEtapa, IdTpAndamento, NmEtapa, NrOrdem, TpAndamento, SiglaComissao

- **55 — Votações nas Comissões**: 55_comissoes_permanentes_votacoes.xml: downloaded, 67514948 bytes. ReuniaoComissaoVotacao (226067 registros): Voto, IdComissao, IdDeputado, IdDocumento, IdPauta, IdReuniao, Deputado, TipoVoto

- **50 — Anotações das Normas**: 50_legislacao_norma_anotacoes.zip: downloaded, 2506698 bytes. NormaAnotacao (68884 registros): DataNormaRel, DsRel, IdNorma, TipoNormaRel, NumNormaRel

- **49 — Normas**: 49_legislacao_normas.zip: downloaded, 10226616 bytes. LegislacaoNorma (254067 registros): Data, Ementa, IdNorma, IdTema, CadDO, DataDO, Numero, PagDO, IdTipo, Promulg, Situacao, URLFicha, Autores

- **47 — Subtemas**: 47_legislacao_subtemas.xml: downloaded, 13464 bytes. SubTema (150 registros): IdSubTema, SubTema

- **46 — Temas**: 46_legislacao_temas.xml: downloaded, 2463 bytes. Tema (36 registros): IdTema, Tema

- **48 — Tipos de Normas**: 48_legislacao_tipo_normas.xml: downloaded, 1106 bytes. TipoNorma (14 registros): IdTipo, DsTipo

- **201 — Eventos**: 201_agenda_eventos.xml: downloaded, 29376777 bytes. Evento (60304 registros): Data, DataProxDia, FlagCancelado, FlagProxDia, FlagTransferido, IdEvento, HoraFim, HoraIni, Local, Obs, Publico, Solicitante, Titulo, Descricao, JustCancel, DataTransferido

## Descoberta posterior: API parlamentar e ponte de nome civil

A página oficial `/deputado/?matricula=300607` contém chamada pública para `https://legis-api-portal-prd.al.sp.gov.br/parlamentar-portal/detalhes/300607`. O host pertence ao mesmo domínio oficial al.sp.gov.br. Os 94 perfis da lista atual foram baixados com URL/hash/coleta em `profile-manifest.json`, totalizando **192 registros de filiação**. Esse endpoint amplia o catálogo XML: o resultado anterior de ausência de datas aplica-se aos XMLs do catálogo, não a toda ALESP.

`listaFiliacoes` possui `idFiliacaoPartidaria`, parlamentar (idParlamentar, nuMatricula), partido (idPartido, nuLegenda, txSigla, txNome) e **dtInicio/dtFim no nível do vínculo**. O objeto `partido` também possui dtInicio/dtFim, que dizem respeito ao cadastro do partido: não confundir os dois níveis. As datas são fatos publicados pelo sistema parlamentar, não prova de todo histórico eleitoral de filiação. Não há garantia de completude fora das legislaturas registradas.

Há `listaMandatos` com idLegislatura, descrição, dtInicio/dtTermino, `isEmExercicio` atual e aniversário DD/MM em biografia. Intervalos de legislatura não comprovam todos afastamentos individuais. `txNomePlenario` está nulo nas amostras examinadas; não foram encontrados CPF ou nascimento completo no esquema. `/autores/{IdSPL}` é acessível e retorna nome parlamentar e matrícula, sem nome civil.

Uma ponte adicional é a lista telefônica oficial: `https://www.al.sp.gov.br/alesp/telefones/?idUA=20455`. IdUA vem dos deputados XML/API. A página relaciona **GABINETE DEP. + nome parlamentar + link com matrícula**, **Responsável: nome civil completo** e, quando publicado, **Cargo: Deputado(a)**. O nome civil pode ser cruzado exatamente com a folha e pessoa TSE, corroborando aniversário e candidatura. Nome do responsável deve ser extraído do elemento p, ignorando comentários HTML; não concatenar e-mail/cargo.

`telephone-manifest.json` preserva os downloads das páginas e `identity-bridge.json` contém a extração limpa com nome responsável, nome parlamentar, aniversário, matrícula, idUA e indicadores de confirmação DOM. Há divergências reais de grafia e sobrenomes entre fontes oficiais; não aplicar fuzzy automático nem corrigir silenciosamente. União precisa guardar método, todas as URLs/hash e conflitos. CPF compartilhado não foi confirmado; a chave operacional ALESP é matrícula e a ponte biográfica requer nome civil mais corroboração.

A coleta telefônica foi concluída: **94 páginas**, com 91 nomes responsáveis iguais aos nomes da folha após normalização de caixa/acentos. 77 páginas explicitam cargo de deputado e 79 repetem link com matrícula; as outras 15 identificam o gabinete pelo cabeçalho textual, sem link. Não há link contraditório para outra matrícula nessas 15 páginas. As três divergências envolvem variação de grafia, sobrenome adicional e abreviação. Estão explicitadas em `identity-bridge-summary.json` para resolução fundamentada, sem normalização destrutiva automática.
