# Fontes de aposentadorias e pensões: SP, RJ e complemento federal

Verificação iniciada em 16/10/2026 e documentação concluída em 17/10/2026 (America/Belem). Pesquisa de páginas oficiais públicas, cabeçalhos de arquivos e dicionários; não houve ingestão previdenciária, acesso a contas de beneficiários ou alteração dos arquivos originais. “Não confirmado” significa que a pesquisa não comprovou o campo, não que ele inexista no órgão.

## Resultado para decisão

A fonte mais barata para começar é o download estadual de SP: CSV/TXT públicos separados em ativos, aposentados e pensionistas, além de ZIP por competência. O cadastro federal é o mais explícito sobre datas e tipos de benefício, mas cobre o Executivo federal, não substitui os estados. RJ tem consultas oficiais próprias, cujo esquema e exportação precisam de uma prova adicional antes de implementar coleta em lote. Nenhuma fonte verificada entrega publicamente, de forma comprovada, todos os campos solicitados com CPF completo e nascimento.

Status deve pertencer ao vínculo ou benefício com período e evidência. Uma pessoa pode exercer mandato e receber aposentadoria, ou acumular aposentadoria e pensão: `active`, `retired` e `pensioner` não são um único enum exclusivo na pessoa. Benefício ativo também não significa servidor em atividade. Ausência na folha não prova cessação.

## São Paulo: Portal da Transparência do Executivo

Página operacional [Relação nominal e remuneração mensal](https://www.transparencia.sp.gov.br/Remuneracaomensal/Index), acessível sem autenticação. A página oferece CSV/TXT por grupo, exportação da consulta e série histórica em ZIP. O intervalo visível nesta verificação foi abril/2023 a julho/2026; isso não comprova inexistência de períodos anteriores ou mais recentes em outros canais.

Endpoints encontrados no HTML e testados com HTTP 200, lendo apenas o início dos arquivos:

- [Aposentados CSV](https://www.transparencia.sp.gov.br/Remuneracao/Download?arquivo=RemuneracaoAposentados.csv).
- [Pensionistas CSV](https://www.transparencia.sp.gov.br/Remuneracao/Download?arquivo=RemuneracaoPensionistas.csv).
- [Ativos CSV](https://www.transparencia.sp.gov.br/Remuneracao/Download?arquivo=RemuneracaoAtivos.csv) — link publicado, download não testado nesta pesquisa.

Cabeçalhos confirmados nos dois primeiros arquivos: nome, CPF, cargo, órgão, remuneração do mês, férias/13º, pagamentos eventuais, licença-prêmio indenizada, abono/indenizações, redutor, total líquido, grupo, situação de desligamento, regime, jornada, referência, grau, ingresso e nomeação. CPF contém máscara nas linhas amostradas. Não há coluna explícita de nascimento, aposentadoria, início da pensão ou fundamento no cabeçalho. `INGRESSO` e `NOMEACAO` não devem ser reinterpretados como datas previdenciárias. Dicionário XLSX é oferecido na página, mas seu conteúdo não foi analisado. Preservar competência obtida do catálogo/arquivo, sem presumir que `REFERÊNCIA` signifique competência.

## ALESP e SPPREV

[ALESP: remuneração dos servidores](https://www.al.sp.gov.br/alesp/folha-de-pagamento/) declara incluir ativos e proventos de inativos e publica HTML mensal. A [amostra agosto/2026](https://www.al.sp.gov.br/repositorio/folha-de-pagamento/folha-2026-08.html) tem nome, bruto, líquido e tributos. Não distingue status por linha nem oferece CPF, nascimento, data do benefício ou fundamento nesses campos. A página de [lotação](https://www.al.sp.gov.br/servidor/) oferece histórico de cargos/lotações. O XML de cargos já analisado no projeto contém `APOSENTADO`; isso é evidência administrativa de cargo/status naquele registro, não comprova concessão ou valor de benefício previdenciário. A folha de deputados ingerida também não informa aposentadoria/pensão.

A [SPPREV](https://www.spprev.sp.gov.br/spprev/institucional/quem%20somos) é fonte institucional para benefícios estaduais, mas a descrição da cobertura contém expansão futura da folha de alguns poderes: não assumir centralização completa. O [informe de rendimentos](https://www.spprev.sp.gov.br/spprev/servi%C3%A7os/informederendimentos) é serviço ao beneficiário; acesso individual exige canal autenticado. Não é base pública para crawler. Não foi encontrada nesta verificação API pública nominal da SPPREV com nascimento e datas de concessão.

## Rio de Janeiro: Executivo e Rioprevidência

A [seção Recursos Humanos da Transparência RJ](https://www.transparencia.rj.gov.br/recursos-humanos/) declara cobertura de ativos, inativos e pensionistas e aponta para [GESPERJ — Consulta Remuneração](https://www.rj.gov.br/remuneracao/). O endereço respondeu HTTP 200, mas retorna estrutura de aplicação dinâmica sem tabela no HTML inicial. Campos individuais, máscara do CPF, período histórico, CSV e API pública não foram confirmados; não construir contrato de ingestão a partir apenas do título.

O [Rioprevidência: Aposentados e Pensionistas](https://www.rj.gov.br/rioprevidencia/aposentadosepensionistas) incorpora [ConectaRP](https://conectarp.rioprevidencia.rj.gov.br/aposentados-pensionistas). Ambos são URLs oficiais verificadas; o iframe respondeu HTTP 200 e seu HTML referencia Turnstile. Não foi contornada a proteção. Campos internos, exportação e histórico continuam pendentes de inspeção normal da interface ou documentação oficial. Consulta de contracheque e informe individual não deve ser confundida com transparência nominal pública.

[ALERJ — Folha de pagamento](https://transparencia.alerj.rj.gov.br/section/report/73) respondeu HTTP 200 por acesso direto e lista arquivos via `/download-spic?file=...`, apontando ao domínio `www2.alerj.rj.gov.br/leideacesso/verArquivo.asp?idArquivo=...`. Os arquivos não foram baixados/analisados nesta pesquisa; formato interno, status e campos previdenciários não confirmados. É alternativa de lote a validar, sem presumir que inclua todos os pensionistas.

## Datas e fundamento: Diários Oficiais

O [DOE SP](https://doe.sp.gov.br/) e seu [acervo histórico](https://diariooficial.imprensaoficial.com.br/) são fontes para atos de concessão/retificação. A [orientação administrativa estadual](https://www.saude.sp.gov.br/coordenadoria-de-recursos-humanos/areas-da-crh/grupo-de-gestao-de-pessoas/ggp/faq/ec-702012) exemplifica datas diferentes de início e publicação da aposentadoria. Ato nominal específico de SP ainda não foi extraído neste levantamento.

O [DOERJ de 11/03/2024](https://www.ioerj.com.br/portal/modules/conteudoonline/mostra_edicao.php?k=81400ED4-7A8FD-4403-9FD8-F63630F94B5F9) foi verificado no texto oficial indexado: atos do Rioprevidência publicam beneficiário, instituidor, tipo de relação, valor inicial, cota, fundamento legal, validade e processo. Essa fonte confirma disponibilidade desses conceitos em atos, mas não garante padronização universal, nascimento, CPF ou valor efetivamente pago em cada competência. Guardar separadamente publicação, vigência, implantação e pagamento; não inferir a data do primeiro crédito a partir da vigência.

Diário é enriquecimento seletivo de casos, de custo maior que CSV. O tipo/fundamento publicado não autoriza inventar motivo médico ou diagnóstico. Diferenciar pensão por morte, militar, especial e alimentícia; beneficiário, instituidor e representante são pessoas distintas.

## Complemento: Executivo federal

O [download mensal de servidores](https://portaldatransparencia.gov.br/download-de-dados/servidores) oferece base em lote. [Dicionário de inativos](https://portaldatransparencia.gov.br/servidores-inativos) confirma nome, CPF/matrícula mascarados, data e tipo de aposentadoria, cargo e situação. [Dicionário de pensionistas](https://portaldatransparencia.gov.br/dicionario-de-dados/servidores-pensionistas) confirma nome, CPF mascarado, início/tipo da pensão, instituidor e órgão. Nascimento e RG não constam nos campos verificados. [Remuneração](https://portaldatransparencia.gov.br/dicionario-de-dados/servidores-remuneracao) complementa valores por arquivo mensal. O ID da fonte serve apenas para juntar os arquivos durante a extração, não como identidade permanente no sistema.

A [FAQ oficial](https://portaldatransparencia.gov.br/perguntas-frequentes/servidores-publicos) explica divulgação individualizada desde junho/2021 e históricos coletados desde 2020. A [API oficial](https://api.portaldatransparencia.gov.br/) documenta consulta de servidor e remuneração; a política de chave/limites não foi validada nesta pesquisa. Preferir lote público. UF de lotação não prova residência nem vínculo eleitoral SP/RJ.

## INSS/RGPS: não há vínculo nominal comprovado

O [catálogo oficial INSS](https://www.gov.br/inss/pt-br/acesso-a-informacao/dados-abertos/dados-abertos) aponta conjuntos de concedidos, mantidos e emitidos. [Concedidos](https://dadosabertos.inss.gov.br/ro/dataset/beneficios-concedidos-plano-de-dados-abertos-jun-2023-a-jun-2025) descreve nascimento, espécie, DIB, despacho e cessação; [mantidos](https://dadosabertos.inss.gov.br/ro/dataset/beneficios-mantidos-plano-de-dados-abertos-jun-2023-a-jun-2025) descreve renda mensal, situação e motivos de suspensão/cessação. Não foi confirmada presença de nome/CPF no esquema público; portanto esses conjuntos não foram aprovados para associação nominal. Um recurso anunciado CSV redirecionou a ZIP/S3 com HTTP 403 na tentativa; catálogo acessível não significa arquivo operacional validado. Não usar nascimento, município e sexo para tentar reidentificar registros sem chave nominal legitimamente publicada.

## Estratégia recomendada

1. Implementar primeiro descoberta e preservação dos CSV/ZIP de SP, validando esquema e competência por artefato; processar em streaming/lotes.
2. Construir índices de dados pessoais para candidatos à associação: CPF completo validado quando disponível, RG com emissor/UF, nome completo e nascimento. CPF mascarado apenas corrobora ou exclui; nunca reconstruí-lo. Partido é contexto temporal, não identidade civil.
3. Vincular ao `person_id` somente com evidência suficiente; homônimos e conflitos ficam pendentes. Nome abreviado isolado é insuficiente.
4. Separar benefício, seu histórico de situação e pagamentos por competência; manter fonte/data/evidência em cada fato, sem códigos externos como identidade permanente. Corrigir fatos preservando versões, sem sobrescrever silenciosamente.
5. Enriquecer datas e fundamento com atos oficiais; inspecionar o acesso público normal de RJ/ALERJ antes de prometer lote. Pedido LAI pode esclarecer layout/cobertura, mas nenhum pedido foi enviado.

Este levantamento documenta viabilidade e limitações; não declara que candidatos específicos são aposentados ou pensionistas. Ocupação declarada ao TSE é autodeclaração eleitoral, não prova de benefício vigente ou pagamento.
