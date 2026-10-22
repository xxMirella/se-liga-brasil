# Fontes oficiais para perfis parlamentares — Se Liga, Brasil

Data do levantamento: **6 de outubro de 2026**. Escopo: deputados federais, senadores, deputados estaduais das 26 assembleias e deputados distritais da Câmara Legislativa do Distrito Federal.

Este é um catálogo de fontes, não uma base de pessoas já coletada. A cobertura geográfica é nacional; a disponibilidade de todos os campos para todas as pessoas não está comprovada. Há fontes estruturadas nacionais e fontes complementares de cada Casa. Nenhuma fonte isolada garante a reconstrução completa da vida pública.

## 1. Como interpretar a verificação

- **Página consultada:** conteúdo recuperado pela ferramenta de pesquisa nesta data. Não implica que todos os perfis individuais foram examinados.
- **Documentação consultada:** forma de acesso descrita oficialmente; não implica teste operacional da API ou importação de um arquivo.
- **Indexada:** conteúdo localizado no índice de pesquisa em domínio oficial; consulta direta pendente ou com falha.
- **Consulta parcial:** portal acessível, mas a listagem ou os campos individuais não puderam ser confirmados.
- **Revalidar acesso:** tentativa de abertura falhou. Isso não prova que o site está fora do ar para outros clientes.

Não foram testadas autenticação, paginação completa, limites de requisição, cobertura histórica integral ou completude dos cadastros. Não foram inventadas rotas de APIs estaduais. A ausência de API documentada neste levantamento significa **não confirmada**, e não que a instituição não tenha API.

## 2. Campos do perfil e fontes de referência

| Dado desejado | Fonte prioritária | Aquisição | Limitação e interpretação |
| --- | --- | --- | --- |
| Nome civil e nome parlamentar/urna | TSE; cadastro da Casa | CSV eleitoral; API federal; página oficial estadual | Preservar os nomes com origem e data; nome sozinho não resolve identidade. |
| Data de nascimento | TSE; cadastro/biografia oficial | CSV; detalhe de perfil quando disponível | Verificar divergências entre eleições e fontes. |
| Idade | Data de nascimento documentada | Calcular para uma data de referência | Não armazenar idade fixa sem data; não inferir nascimento de uma idade em notícia. |
| Escolaridade | TSE; Câmara e biografias oficiais | CSV; API; HTML | Escolaridade declarada não identifica necessariamente curso, instituição ou diploma. |
| Formação acadêmica: curso, instituição, conclusão | Biografia publicada pela Casa | HTML/documento oficial, revisão humana | Campo opcional; profissão e tratamento como “Dr.” não comprovam formação. |
| UF de atuação/representação | Cadastro da Casa; TSE | API, CSV ou vínculo com a Casa estadual | Separar UF representada, UF de candidatura e UF de nascimento. |
| Cargo público | Casa legislativa e seus atos | Cadastro atual; ato de posse; histórico | Candidatura, eleição e exercício são fatos diferentes. |
| Início e fim no cargo | Histórico de mandatos; atos de posse, licença, retorno e desligamento | API federal; SAPL quando documentado; HTML; diário oficial | Datas da legislatura não são necessariamente datas de exercício da pessoa. |
| Anos de atuação no cargo | Intervalos de exercício confirmados | Dado derivado dos intervalos documentados | Não contar licenças nem duplicar períodos sobrepostos; explicitar método de cálculo. |
| Primeira candidatura conhecida | TSE em diferentes eleições | Downloads históricos | É a primeira candidatura na cobertura pesquisada, não o início da vida pública. |
| Primeiro mandato eletivo conhecido | Histórico da Casa; TSE como apoio; atos de posse | API, biografia e documentos | Resultado eleitoral não comprova data efetiva de posse. |
| Início declarado da vida pública | Biografia oficial e atos de cargos anteriores | Texto/documento e revisão humana | Pode envolver cargo nomeado, militância ou movimento social. Guardar significado e evidência; não reduzir tudo à primeira eleição. |
| Partido | Casa para situação atual; TSE para eleição | API/HTML e CSV por eleição | Filiação na eleição não representa obrigatoriamente o partido atual. |
| Foto e contatos institucionais | Casa; TSE | URL oficial ou arquivos disponíveis | Registrar origem e verificar condições de reutilização dos recursos. |

## 3. Fontes nacionais e federais

### N01 — TSE: Portal de Dados Abertos

- **Responsável:** Tribunal Superior Eleitoral.
- **Links:** [portal](https://dadosabertos.tse.jus.br/), [grupo de candidatos](https://dadosabertos.tse.jus.br/pt_BR/group/candidatos), [Candidatos — 2022](https://dadosabertos.tse.jus.br/dataset/candidatos-2022).
- **Abrangência:** candidaturas de todo o Brasil, incluindo deputado estadual, distrital, federal e senador. Consultar diferentes anos para histórico; incluir eleições municipais para localizar candidaturas anteriores a vereador/prefeito.
- **Tipo de dado:** identificação eleitoral, nome civil/urna, nascimento, escolaridade declarada, ocupação, partido, UF, cargo disputado e situação eleitoral conforme o arquivo/dicionário do ano. Também há recursos de bens, fotos e informações complementares.
- **Aquisição:** abrir o conjunto da eleição; selecionar o recurso “Candidatos”; seguir o link oficial de download; baixar e descompactar o ZIP com CSVs; ler o leiaute associado. Filtrar por UF e cargo. Conferir cabeçalhos, codificação, delimitador, valores ausentes e data de geração antes da importação.
- **Campos a conferir no leiaute:** `NM_CANDIDATO`, `NM_URNA_CANDIDATO`, `DT_NASCIMENTO`, `DS_GRAU_INSTRUCAO`, `DS_OCUPACAO`, `SG_UF`, `DS_CARGO`, `SG_PARTIDO`, `SQ_CANDIDATO`, `ANO_ELEICAO` e campos de situação/resultado quando presentes. Os nomes devem ser revalidados por ano.
- **Relacionamento:** `SQ_CANDIDATO` deve ser contextualizado pela eleição. Não pressupor identificador pessoal único entre todos os anos. Não expor identificadores pessoais desnecessários no perfil público.
- **Limites:** candidatura não prova exercício; cadastro declaratório não é comprovação acadêmica; a primeira ocorrência histórica depende da cobertura dos conjuntos.
- **Verificação:** página de 2022 consultada; confirmou recurso de candidatos para todas as UFs, arquivos de fotos e bens. CSVs não foram importados neste levantamento.

### N02 — TSE: DivulgaCandContas

- **Link:** [consulta pública](https://divulgacandcontas.tse.jus.br/divulga/).
- **Tipo de dado:** consulta individual de candidatura e informações eleitorais disponibilizadas pelo sistema.
- **Aquisição:** selecionar eleição, UF, cargo e candidato na interface pública. Para carga em lote, priorizar N01; não tratar chamadas internas do site como API pública documentada.
- **Uso:** conferir uma candidatura e guardar a referência correspondente. Não substitui a lista atual de parlamentares em exercício.
- **Verificação:** referência complementar; interface não validada operacionalmente neste levantamento.

### F01 — Câmara dos Deputados: Dados Abertos

- **Responsável:** Câmara dos Deputados.
- **Links:** [documentação da API e arquivos](https://dadosabertos.camara.leg.br/swagger/api.html), [portal](https://dadosabertos.camara.leg.br/).
- **Abrangência:** deputados federais; cadastro atual e histórico disponível nos serviços.
- **Tipo de dado:** nome civil/parlamentar, identificador da Câmara, foto, nascimento, escolaridade, UF, partido e situação conforme serviço; histórico parlamentar, ocupações, profissões e mandatos externos em consultas próprias.
- **Aquisição:** HTTP GET à API REST, JSON ou XML, sem cadastro indicado para essas consultas na documentação. Listar pessoas, seguir paginação, consultar detalhe e histórico pelo ID oficial. Para cargas amplas, avaliar arquivos oficiais.
- **Rotas documentadas:** `/api/v2/deputados`; `/api/v2/deputados/{id}`; `/api/v2/deputados/{id}/historico`; `/api/v2/deputados/{id}/mandatosExternos`; `/api/v2/deputados/{id}/profissoes`; `/api/v2/deputados/{id}/ocupacoes`.
- **Exemplo de URL:** [listagem](https://dadosabertos.camara.leg.br/api/v2/deputados). `{id}` é um parâmetro a obter na listagem, não uma URL literal pronta.
- **Limites:** profissão não equivale a formação; mandatos externos precisam de avaliação de completude; histórico de estado parlamentar precisa ser interpretado para calcular exercício. A API informa estar incompleta.
- **Verificação:** documentação consultada. A tentativa de recuperar uma resposta de exemplo pela ferramenta de pesquisa falhou; integração operacional não validada.

### F02 — Câmara dos Deputados: biografias e memória

- **Link:** [área de deputados](https://www.camara.leg.br/deputados/).
- **Tipo de dado:** perfil individual e referências biográficas, inclusive trajetória anterior quando publicada.
- **Aquisição:** localizar pessoa na busca oficial; abrir biografia/histórico; extrair texto com referência por afirmação. Usar para complementar F01.
- **Limites:** não presumir todos os cursos, cargos ou início de vida pública; conteúdo biográfico requer revisão e pode ser declaratório.
- **Verificação:** fonte complementar institucional; campos de todas as biografias não auditados.

### F03 — Senado Federal: Dados Abertos legislativos

- **Responsável:** Senado Federal.
- **Links:** [catálogo de senadores](https://www12.senado.leg.br/dados-abertos/conjuntos?grupo=senadores&portal=Legislativo), [senadores em exercício e serviços relacionados](https://www12.senado.leg.br/dados-abertos/legislativo/parlamentares/senadores-em-exercicio), [portal de dados abertos](https://www12.senado.leg.br/dados-abertos).
- **Abrangência:** senadores em exercício e históricos dos mandatos conforme serviço; considerar titulares, suplentes e afastamentos.
- **Tipo de dado:** identificação, nome, partido, UF, foto, contato, detalhes do parlamentar, mandatos, filiações no exercício, cargos e comissões. Nascimento/formação devem ser conferidos no detalhe e na biografia; não são garantidos na listagem.
- **Aquisição:** selecionar no catálogo os serviços de lista atual, detalhe, detalhes históricos, mandatos e partidos. Consumir os webservices e formatos oficialmente indicados (XML/JSON/CSV conforme conjunto), preservando o código de parlamentar.
- **Exemplo de serviço:** [lista atual](https://legis.senado.leg.br/dadosabertos/senador/lista/atual). Obter as demais URLs pelo catálogo oficial, sem adivinhar caminhos.
- **Limites:** eleição e mandato titular não bastam para identificar exercício de suplentes; combinar mandatos e afastamentos. A formação completa pode exigir HTML.
- **Verificação:** catálogo e descrição dos serviços consultados; chamada direta ao exemplo não recuperada pela ferramenta de pesquisa. Não houve teste de integração.

### F04 — Senado Federal: perfis individuais

- **Link:** [senadores](https://www25.senado.leg.br/web/senadores/).
- **Tipo de dado:** perfis e biografias, referências a trajetória e cargos anteriores quando publicados.
- **Aquisição:** localizar o perfil oficial pelo código/nome do senador e seguir suas páginas biográficas. Complementar F03 e N01 com evidência por campo.
- **Limites:** biografia não é histórico administrativo completo; escolaridade e trajetória podem depender de texto não padronizado.
- **Verificação:** referência institucional complementar; disponibilidade de cada campo precisa de inspeção individual.

## 4. Fontes estaduais e distrital — cobertura das 27 UFs

Todos os deputados estaduais/distritais também podem ser pesquisados em **N01/TSE** para nome, nascimento, escolaridade declarada, cargo de candidatura e UF. As fontes abaixo confirmam ou complementam a relação com a Casa, a situação atual e o histórico. O cargo é deputado estadual, salvo DF, onde é deputado distrital.

**Regra para esta tabela:** “perfil” significa acesso a páginas individuais ou área correspondente; não garante que todas contenham nascimento, formação e trajetória. Esses três campos são opcionais até inspeção individual. Onde a lista não pôde ser lida, isso está explícito.

| UF | Fonte oficial e link | Tipo de dado confirmado/localizado | Forma de adquirir | Situação da verificação |
| --- | --- | --- | --- | --- |
| AC | ALEAC: [parlamentares no SAPL](https://sapl.al.ac.leg.br/parlamentar/); [dados abertos](https://app.al.ac.leg.br/dados-abertos) | Nome parlamentar, partido, ativo/titular; documentação menciona deputados, mesa e comissões | HTML da lista e perfis; API SAPL pelo Swagger oficialmente indicado; consultar mandatos no esquema | Lista e documentação consultadas |
| AL | Assembleia de Alagoas: [20ª legislatura](https://www.al.al.leg.br/processo-legislativo/20-a-legislatura) | Nome civil/parlamentar, partido, foto, contato; pessoas fora do exercício e motivos publicados | HTML; seguir links individuais para SAPL; cruzar com atos de posse/licença | Listagem consultada |
| AP | Assembleia do Amapá: [portal](https://al.ap.leg.br/); [eLegis](https://elegis.al.ap.leg.br/portal/sessao/1635) | Área Parlamentares; atas com identificação e participação; listagem individual não carregada no texto recuperado | Navegar em Parlamentares; extrair HTML/atas; usar TSE para cadastro e diário para posse | Portal e exemplo de sessão consultados; lista de perfis pendente |
| AM | ALEAM: [deputados](https://www.aleam.gov.br/deputados/) | Nome, partido, função na mesa; links individuais | HTML da lista e perfis; diário para exercício; SAPL vinculado no portal para atividade legislativa | Listagem consultada |
| BA | ALBA: [deputados estaduais](https://www.al.ba.gov.br/deputados/deputados-estaduais); [exemplo de perfil atual](https://www.al.ba.gov.br/deputados/deputado-legislatura-atual/932116) | Lista; biografias com cargos anteriores, mandatos e datas em exemplos oficiais | HTML por perfil; converter texto de mandatos/formação com revisão; conferir posse | Páginas indexadas; abertura do portal teve falha |
| CE | ALECE: [portal](https://www.al.ce.gov.br/) → Parlamentares; História → Deputados na História | Links para parlamentares, mesa e acervo histórico; campos completos individuais não auditados | Navegar pelos links oficiais; HTML de perfis e acervo; documentos de posse | Portal e navegação consultados |
| DF | CLDF: [portal e lista de deputados](https://www.cl.df.gov.br/inicio) | Nome, partido e links individuais dos deputados distritais | HTML do portal e perfis; histórico e atos para início/fim de exercício | Lista no portal consultada |
| ES | ALES: [portal](https://www.al.es.gov.br/); [Centro de Memória](https://cartadeservicos.al.es.gov.br/carta-de-servico/servico/23/centro-de-memoria-e-bens-culturais) | Fonte institucional e acervo histórico documentado; lista/perfis não confirmados nesta consulta | Revalidar portal e localizar Parlamentares; TSE para cadastro; acervo/diário para história | Portal não recuperado; serviço de memória indexado |
| GO | ALEGO: [em exercício](https://portal.al.go.leg.br/deputados/em-exercicio); [portal](https://portal.al.go.leg.br/) | Lista em exercício; navegação separa fora do exercício e legislaturas anteriores | HTML da lista e perfis; histórico por legislatura; atos para intervalos | Listagem e navegação consultadas |
| MA | ALEMA: [deputados](https://www.al.ma.leg.br/sitealema/deputados/) | Lista e seção de licenciados; exemplos de formação em texto | HTML de perfis; diário para alterações de exercício; TSE para campos eleitorais | Página indexada; portal direto não recuperado |
| MT | ALMT: [portal](https://www.al.mt.gov.br/); [ato oficial de composição parlamentar](https://diariooficial.al.mt.gov.br/publicacoes/34283/) | Ato com nomes civis/parlamentares e blocos; perfis atuais não confirmados | HTML do diário e documentos; revalidar área de deputados; TSE para dados pessoais eleitorais | Diário indexado; portal não recuperado |
| MS | ALEMS: [portal](https://al.ms.gov.br/) → Fale com seu deputado; [diário](https://diariooficial.al.ms.gov.br/) | Navegação para contato parlamentar e diário; perfis completos não auditados | Seguir lista/contatos e perfis; HTML; diário para posse/licença | Portal e links consultados |
| MG | ALMG: [legislatura atual](https://www.almg.gov.br/a-assembleia/deputados/inicial/); [API documentada](https://dadosabertos.almg.gov.br/documentacao/index) | Nome, partido, situação, contato, legislatura; dados legislativos via API | API conforme documentação para dados disponíveis; HTML dos perfis para complementos | Lista consultada; documentação localizada |
| PA | ALEPA: [deputados](https://www.alepa.pa.gov.br/Institucional/Deputados) | Listagem oficial e links de deputados | HTML da lista e perfil; diário oficial e histórico para mandato | Listagem consultada |
| PB | ALPB: [deputados](https://www.al.pb.leg.br/categoria/deputados); [perfis da posse de 2023](https://www.al.pb.leg.br/47580/conheca-os-36-deputados-empossados-nesta-quarta-pela-assembleia.html) | Lista e perfis em publicação de posse; exemplos de formação, trajetória e cargos anteriores | HTML por perfil; publicação de 2023 como histórico, nunca como prova isolada de exercício atual | Páginas indexadas; abertura do portal teve falha |
| PE | ALEPE: [portal](https://www.alepe.pe.gov.br/); [publicação oficial sobre comissões](https://www.alepe.pe.gov.br/2025/02/15/comissoes-definem-presidentes-em-reunioes-sem-a-bancada-governista/) | Fonte institucional e notícia parlamentar; lista/perfis não recuperados | Revalidar portal e localizar Deputados; HTML e diário; N01 para cadastro | Conteúdo oficial indexado; portal/lista não recuperados |
| PI | ALEPI: [portal](https://www.al.pi.leg.br/) | Áreas Deputados e Deputados licenciados; conteúdo individual não carregado no texto recuperado | Abrir áreas no portal; extrair lista/perfis; TSE e diário para lacunas | Consulta parcial |
| PR | ALEP: [conheça os deputados](https://www.assembleia.pr.leg.br/deputados/conheca) | Lista e links de deputados; navegação para representação partidária | HTML da lista/perfis; diário e documentos para exercício | Listagem consultada |
| RJ | ALERJ: [quem são](https://www.alerj.rj.gov.br/Deputados/QuemSao) | Lista de deputados; representação partidária em área própria | HTML dos perfis; histórico e atos oficiais para datas | Listagem consultada |
| RN | ALRN: [deputados](https://www.al.rn.leg.br/deputados) | Nome, partido, fotos/links individuais | HTML de lista e perfis; documentos e diário para mandato | Listagem consultada |
| RS | Assembleia do RS: [portal](https://www.al.rs.gov.br/) | Portal institucional identificado; cadastro individual não confirmado nesta consulta | Revalidar acesso e localizar Deputados; TSE para cadastro; diário/acervo para exercício | Revalidar acesso; falha nas tentativas de abertura |
| RO | ALERO: [perfil dos deputados](https://www.al.ro.leg.br/deputados/perfil/) | Lista e perfis; portal vincula SAPL para comissões e frentes | HTML dos perfis; documentos/SAPL quando acesso documentado for confirmado | Listagem consultada |
| RR | ALE-RR: [legislatura atual](https://al.rr.leg.br/deputados-estaduais-2023/); [portal](https://al.rr.leg.br/) | Deputados atuais; links de legislaturas anteriores no portal | HTML e páginas individuais; histórico por legislatura; diário para exercício | Lista e navegação consultadas |
| SC | ALESC: [deputados](https://www.alesc.sc.gov.br/deputados/) | Lista e perfis oficiais | HTML de lista e perfis; diário e acervo para história | Listagem consultada |
| SP | ALESP: [lista](https://www.al.sp.gov.br/deputado/lista/); [dataset de deputados](https://ckan.al.sp.gov.br/group/deputados-estaduais/dataset/deputados) | Lista, perfis; dataset XML da legislatura atual; acervo “Parlamentares desde 1947” no portal | Download XML via recurso do catálogo; HTML de perfis e acervo histórico | Lista consultada; dataset indexado |
| SE | ALESE: [parlamentares no Alese Legis](https://aleselegis.al.se.leg.br/spl/parlamentares.aspx) | Lista, identificação e links individuais | HTML do sistema legislativo e perfis; atas/diário para datas | Listagem consultada |
| TO | ALETO: [portal](https://www.al.to.leg.br/); [mesa diretora com perfis](https://al.to.leg.br/mesaDiretora) | Biografias de integrantes da mesa com mandatos e trajetória em exemplos; lista geral não confirmada | HTML dos perfis; localizar lista geral via portal; TSE para todos; diário para posse | Portal consultado; mesa indexada; lista geral pendente |

### 4.1. Acesso estruturado estadual confirmado na documentação

**Acre — SAPL:** a [página oficial de dados abertos](https://app.al.ac.leg.br/dados-abertos) indica explicitamente [Swagger do SAPL](https://sapl.al.ac.leg.br/api/schema/swagger-ui/). Obter no esquema os recursos de parlamentar, legislatura, mandato e filiação efetivamente expostos. Não transportar automaticamente essas rotas para SAPLs de outras UFs.

**Minas Gerais — API própria:** [documentação da ALMG](https://dadosabertos.almg.gov.br/documentacao/index). Escolher serviços disponíveis na versão atual e verificar formato, parâmetros, paginação e quais campos biográficos o serviço realmente devolve. A existência da API não garante todos os campos deste documento.

**São Paulo — arquivos XML:** [dataset oficial de deputados](https://ckan.al.sp.gov.br/group/deputados-estaduais/dataset/deputados). O recurso publicado aponta para [deputados.xml](https://www3.al.sp.gov.br/repositorio/dados-abertos/output/xml/deputados/deputados.xml). Baixar o recurso vigente do catálogo, analisar elementos/atributos e combinar com perfis. O conjunto descrito é da legislatura atual, não um arquivo histórico completo. Download não executado neste levantamento.

Para as demais UFs, o método inicial confirmado ou recomendado é consulta de páginas/documentos oficiais. APIs só devem ser adicionadas depois de documentação ou resposta efetivamente validada e atribuída ao órgão.

### 4.2. Exemplos oficiais de enriquecimento biográfico

- **Bahia — formação:** [perfil histórico com seção Formação Educacional](https://www.al.ba.gov.br/deputados/deputado-estadual/5000022). Demonstra que a ALBA publica detalhes acadêmicos em pelo menos parte das biografias; não comprova cobertura para todos.
- **Bahia — cargos anteriores:** [perfil de legislatura atual](https://www.al.ba.gov.br/deputados/deputado-legislatura-atual/932116). Inclui exemplo de cargo de chefe de gabinete anterior ao mandato eletivo.
- **Paraíba — trajetória na posse:** [perfis da legislatura iniciada em 2023](https://www.al.pb.leg.br/47580/conheca-os-36-deputados-empossados-nesta-quarta-pela-assembleia.html). Há exemplos de cargos anteriores e ingresso na política. Tratar a publicação como retrato daquela data.
- **Tocantins — trajetória:** [mesa diretora](https://al.to.leg.br/mesaDiretora). Inclui exemplos de mandatos anteriores e primeiro cargo eletivo. Cobertura restrita aos perfis apresentados nessa página.

## 5. Como adquirir e reconciliar os dados

1. **Inventário atual:** começar pela relação em exercício da Câmara, Senado e cada Casa estadual/distrital. Registrar separadamente eleitos para a próxima legislatura, titulares licenciados e suplentes em exercício.
2. **Base eleitoral nacional:** baixar os candidatos do TSE para os anos relevantes; selecionar cargos/UF e associar candidaturas à pessoa, com evidência suficiente. Pesquisar anos municipais para trajetórias anteriores.
3. **Enriquecimento:** consumir APIs documentadas da Câmara, Senado, ALEAC e ALMG e XML da ALESP; complementar com páginas individuais das Casas.
4. **Exercício:** conferir posse, licença, retorno, renúncia e encerramento de cada intervalo. Guardar a URL do ato ou registro administrativo que sustenta cada data.
5. **Biografias:** extrair formação e início da vida pública apenas quando publicados explicitamente. Guardar a afirmação original e sua referência; revisão humana para textos ambíguos.
6. **Lacunas:** quando o cadastro ou histórico não estiver acessível, usar o SIC/e-SIC da própria instituição para solicitar arquivo público estruturado ou referência oficial. Pedido não foi enviado neste trabalho.
7. **Atualização:** definir frequência após medir atualização das fontes; registrar a data da coleta e a data efetiva do registro, que podem ser diferentes.

HTML requer extração de conteúdo público com adaptação por instituição; páginas com JavaScript podem precisar de navegação de navegador. Priorizar downloads/API publicados pelo órgão. Não contornar controles de acesso nem assumir que uma chamada interna é API pública estável.

## 6. Rastreabilidade por campo

Cada afirmação do perfil deve guardar:

| Metadado | Finalidade |
| --- | --- |
| Fonte e órgão responsável | Identificar quem publicou o dado |
| URL da página/recurso e ID oficial | Permitir conferência e reconciliação |
| Campo e valor original | Evitar perder informação na normalização |
| Valor normalizado | Exibir e pesquisar de forma consistente |
| Data de coleta e competência/data do registro | Diferenciar atualização de validade |
| Método de aquisição | API, download, HTML, documento ou resposta do SIC |
| Cobertura temporal | Informar quais anos/mandatos foram pesquisados |
| Natureza da evidência | Registro administrativo, declaração eleitoral, biografia ou cálculo |
| Estado de revisão | Confirmado na fonte, divergente, incompleto ou a revisar |
| Regra do cálculo, quando derivado | Explicar idade e duração do exercício |

Não substituir informações divergentes silenciosamente. Preservar as duas evidências e decidir qual se aplica ao período e ao significado do campo.

## 7. Lacunas e próximos testes de aquisição

- **Cobertura de perfis:** há uma fonte nacional (TSE) para todos os recortes eleitorais e entradas institucionais para as 27 UFs. Isso ainda não é comprovação de cadastro atual completo de todos os parlamentares.
- **Revalidar prioridade:** portais de ES e RS; perfis atuais de MT; lista geral de PE; carregamento individual de AP e PI; lista geral de TO.
- **Histórico:** biografia e período de legislatura não substituem intervalos administrativos de exercício. Não preencher anos de atuação apenas multiplicando quantidade de eleições.
- **Formação:** separar escolaridade, curso e profissão; indicar “não localizado” quando ausente.
- **Vida pública:** manter campos distintos para primeira candidatura conhecida, primeiro mandato conhecido, primeiro cargo público conhecido e início declarado da vida pública.
- **Operação:** testar ao menos uma pessoa e um histórico em cada instituição antes de implementar coleta em lote; conservar exemplo de resposta e data de validação.
- **Mudanças eleitorais:** eleitos em 2026 não devem aparecer automaticamente como ocupantes do cargo antes da posse.
- **AP:** o próprio portal consultado informa migração para eLegis e possível defasagem das informações durante o processo; validar período e completude da extração.

## 8. Critério de conclusão da próxima etapa

A coleta só poderá ser declarada validada por instituição quando houver: lista recuperada com período/situação definidos; perfil individual inspecionado; campos realmente disponíveis documentados; método de aquisição testado; exemplos de posse/afastamento quando necessários; identificadores reconciliados; lacunas registradas. Este levantamento conclui o **catálogo inicial de fontes**, não essa validação operacional.


### Remuneração nominal do Senado — fonte validada em 22/10/2026

O serviço administrativo oficial publica a folha nominal em
`https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/{ano}/{mes}`.
A resposta JSON inclui nomes, competência, tipo de folha e componentes financeiros,
sem CAPTCHA nas consultas verificadas. Identidade exige cruzamento com evidência
pessoal oficial; `sequencial` não é intercambiável entre cadastro e folha.

Contrato, exemplos, regras de associação e cálculo:
[API nominal de remunerações do Senado](fonte-api-remuneracao-senado.md).
