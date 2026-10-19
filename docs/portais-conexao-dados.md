# Portais oficiais que conectam identidade, vínculos e pagamentos

Verificação em 17/10/2026, America/Belem. Pesquisa oficial e amostras públicas; nenhuma alteração no banco, pedido LAI ou reconstrução de CPF. Complementa `cobertura-crawlers-pendencias.md` e `fontes-previdenciarias.md`.

## Conclusão

Existem conexões oficiais parciais, mas não foi encontrado um portal que entregue todos os campos de todas as pessoas candidatas. A Câmara é a conexão pessoal mais forte já operacional no projeto. O cadastro PEP da CGU é um novo complemento barato para descobrir cargos de diferentes poderes/esferas em um único lote. Os portais de servidores conectam cadastro funcional e pagamento dentro de sua cobertura; não substituem TSE, casas legislativas nem resolução segura de identidade.

## CGU: pessoas politicamente expostas — operacional, arquivo validado

[Download oficial PEP](https://portaldatransparencia.gov.br/download-de-dados/pep) e [dicionário](https://portaldatransparencia.gov.br/dicionario-de-dados/pep). A página anuncia pessoas que exercem ou exerceram funções relevantes e informa múltiplos fornecedores institucionais; não é cadastro universal de todos os empregos públicos.

O catálogo HTML anunciou agosto/2026. O [download anunciado](https://portaldatransparencia.gov.br/download-de-dados/pep/202608) respondeu HTTP 200 e redirecionou para `dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/pep/202608_PEP.zip`. Amostra integral validada: 2.498.594 bytes, CSV CP1252, 133.880 registros. Campos: CPF, nome, sigla/descrição/nível da função, órgão, início/fim do exercício e fim da carência. Todos os 133.880 CPFs estão mascarados; nenhum tem 11 algarismos publicados.

Original preservado em `data/research/transparency-links/202608_PEP.zip`; metadados, hash e contagens em `pep-validation-2026-10-17.json`. Nenhuma linha nominal foi ingerida. O arquivo é uma fotografia, não uma prova de atualização diária. Não contém nascimento, salário, escolaridade, partido ou patrimônio. Fim da carência PEP não é fim do cargo; PEP pode ser ex-ocupante. Cargo com fim vazio exige avaliação da competência e confirmação institucional atual. Ausência não comprova que a pessoa não tenha cargo.

Recomendação: futuro `crawlers/cgu_pep/` para descoberta e evidência complementar, um download por versão. Nome e CPF parcial sugerem candidatos à associação, mas precisam de identificação corroborada antes de ligar ao `person_id`.

## CGU: cadastro de servidores + remuneração + benefícios — conexão documentada

[Cadastro atual](https://portaldatransparencia.gov.br/dicionario-de-dados/servidores-cadastro) documenta nome, CPF/matrícula mascarados, cargo, função, órgãos de lotação/exercício, situação, afastamento e datas funcionais. [Remuneração](https://portaldatransparencia.gov.br/dicionario-de-dados/servidores-remuneracao) documenta competência, bruto, deduções e indenizações em componentes separados. Os arquivos compartilham `ID_SERVIDOR_PORTAL`: permite juntar arquivos durante o processamento; não deve virar identidade civil persistente no sistema. Nenhum nascimento/RG consta nesses dois esquemas verificados.

[Inativos](https://portaldatransparencia.gov.br/servidores-inativos) e [pensionistas](https://portaldatransparencia.gov.br/dicionario-de-dados/servidores-pensionistas) têm cadastros próprios. O segundo distingue beneficiário, representante e instituidor e informa início da pensão. Não atribuir o cargo do instituidor ao beneficiário.

O [download mensal](https://portaldatransparencia.gov.br/download-de-dados/servidores) está publicado; não baixei os lotes grandes nesta pesquisa. A [API documentada](https://api.portaldatransparencia.gov.br/) anuncia consulta de servidor e remuneração por CPF ou identificador; autenticação/limites não foram testados. A [FAQ oficial](https://portaldatransparencia.gov.br/perguntas-frequentes/servidores-publicos) delimita Executivo federal e exclui outros poderes/esferas sem vínculo federal e diversas empresas públicas. Isso impede usar a CGU como prova universal de ausência de cargo.

Recomendação: conector `crawlers/transparencia_federal/` somente para vínculos pertinentes; preferir lotes e junção temporária local. CPF mascarado não é chave única para nosso banco.

## Câmara — API pessoal operacional; salário em canal separado

[API e documentação](https://dadosabertos.camara.leg.br/swagger/api.html) e [arquivos em lote](https://dadosabertos.camara.leg.br/). Requisição direta ao perfil já usado pelo projeto respondeu HTTP 200 nesta pesquisa. Campos confirmados: nome civil, CPF completo de 11 algarismos, nascimento, escolaridade e último status. Valores de CPF não foram impressos nem duplicados em novo arquivo.

Essa amostra permite associação por CPF validado com o TSE; nome e nascimento corroboram. Histórico/exercício e proposições são serviços relacionados. A remuneração nominal é obtida pela folha no portal institucional, não pela despesa parlamentar: cotas, reembolsos e verbas de gabinete não são salário. O crawler Câmara existente já implementa essa composição; não criar outro. A [documentação do webservice legado](https://www2.camara.leg.br/transparencia/dados-abertos/dados-abertos-legislativo/webservices/deputados) também anuncia períodos de exercício e filiações; validar detalhes antes de eventual complemento histórico.

## Senado — API operacional; identidade exige perfil complementar

[Catálogo legislativo](https://www12.senado.leg.br/dados-abertos/legislativo/parlamentares), [lista atual](https://legis.senado.leg.br/dadosabertos/senador/lista/atual) e uma consulta de detalhe responderam HTTP 200 por requisições diretas com `Accept: application/json`. Lista contém nome parlamentar/completo, partido, UF, mandato, titularidade/suplentes e períodos de exercício. O detalhe usa o modelo `https://legis.senado.leg.br/dadosabertos/senador/{codigo}.json` e contém `DataNascimento`, naturalidade e UF. Não encontrei CPF/RG nesses campos amostrados. Nome completo + nascimento podem sustentar associação se únicos e consistentes com TSE; partido é contexto temporal.

[Dados administrativos de senadores](https://www12.senado.leg.br/dados-abertos/administrativo/senadores) e [consulta de remuneração](https://www.senado.leg.br/transparencia/rh/servidores/consulta_remuneracao.asp) publicam canais adicionais; a segunda anuncia CSV, mas não prova que sua folha de servidores seja folha de senadores. Arquivo específico de pagamento parlamentar ainda deve ser validado. Reaproveitar o crawler Senado em implementação, sem prometer salário confirmado pela mera tabela legal de subsídio.

## ALESP — composição já parcialmente disponível localmente

[Catálogo de deputados/partidos](https://www.al.sp.gov.br/dados-abertos/grupo/2), [processo legislativo](https://www.al.sp.gov.br/dados-abertos/grupo/1) e [folha institucional](https://www.al.sp.gov.br/alesp/folha-de-pagamento/). Não há nova chave universal comprovada nesta pesquisa. O projeto já preserva XML, perfis, históricos e folhas; deve reaproveitá-los e as identidades revisadas antes de novas chamadas. Perfis e autoria são relacionados pelos códigos técnicos apenas na extração; a ligação permanente permanece no `person_id`. Nome isolado de folha não basta para identificar homônimos.

## Executivo SP — lote remuneratório operacional; bens em consulta adicional

[Relação nominal mensal](https://www.transparencia.sp.gov.br/Remuneracaomensal/Index) oferece CSV/TXT por grupo e ZIP histórico. Os cabeçalhos e downloads de aposentados/pensionistas já foram validados em `fontes-previdenciarias.md`: nome, CPF mascarado, cargo, órgão, valores, situação, regime e datas de ingresso/nomeação. Sem nascimento ou data explícita de concessão no cabeçalho. Essa conexão cobre Executivo estadual, não toda pessoa candidata.

A página [Pessoal](https://www.transparencia.sp.gov.br/home/servidor) agora também aponta [declarações de bens de autoridades](https://www.transparencia.sp.gov.br/Home/Declaracoes). Página acessível, mas documentos internos/layout/identificação e cobertura não foram validados: fonte complementar publicada, ainda não aprovada para ingestão. Declaração de autoridade e declaração eleitoral são fatos de escopo e data diferentes; não sobrescrever uma pela outra.

## RJ e ALERJ — cobertura anunciada, junção pessoal ainda por validar

[Recursos humanos RJ](https://www.transparencia.rj.gov.br/recursos-humanos/) publica canais de ativos/inativos/pensionistas e encaminha ao [GESPERJ](https://www.rj.gov.br/remuneracao/). [ConectaRP](https://conectarp.rioprevidencia.rj.gov.br/aposentados-pensionistas) está publicado para consulta previdenciária. Esquema/exportação/chaves continuam não confirmados; não contornar proteção de acesso. O portal estadual descreve suas fontes SIGRH e SIAFE, mas integração administrativa interna não comprova exportação nominal unificada pública.

[ALERJ folha](https://transparencia.alerj.rj.gov.br/section/report/73) tem catálogo público operacional com arquivos mensais. Pesquisa de campos e ligação pessoal pertence ao agente do crawler ALERJ; esta pesquisa não declara que nascimento/CPF estejam presentes nesses arquivos. Não usar ausência no Executivo RJ para classificar deputado estadual como sem cargo.

## Fluxo recomendado e flag de cargo atual

1. Usar primeiro os artefatos locais do TSE, ALESP e Câmara e seus índices pessoais. Reconciliar conflitos antes de buscar novamente.
2. Resolver vínculos legislativos em lotes por instituição, com exercício e vigência explícitos. Somente depois consultar PEP e portais executivos pertinentes como complemento; não despachar 15 mil consultas individuais por nome.
3. Fazer junções técnicas no processamento e guardar fatos ligados ao UUID interno. CPF completo validado é evidência mais forte; nome completo/nascimento exigem unicidade; RG exige emissor/UF. CPF parcial e partido não decidem identidade sozinhos.
4. Projetar cargo atual na pessoa com flag de três estados: verdadeiro quando exercício atual comprovado; falso somente com evidência suficiente para o escopo avaliado; desconhecido enquanto cobertura/identidade não permitem conclusão. Não converter ausência de folha ou candidatura não eleita em falso universal.
5. Preservar múltiplos vínculos em tabela própria: mandato, emprego e benefício podem coexistir. Aposentado/pensionista não significa automaticamente sem cargo. A projeção resumida na pessoa precisa de data de verificação e fonte, mantendo fatos anteriores.
6. Cache por artefato/competência, uma aquisição por fonte e lote, streaming e índices; revalidar somente o domínio vencido. A fila registra trabalho pendente; evidências oficiais resolvidas permanecem nas tabelas de fatos conforme política do projeto.

Nenhuma das fontes confirmadas fornece histórico partidário universal, patrimônio atual verificado e todos os vínculos de uma pessoa numa única resposta. Essas lacunas continuam dependentes de fontes e regras específicas.
