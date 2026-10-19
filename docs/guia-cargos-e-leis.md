# Guia público de cargos e leis

Rota local: `/como-funciona`. A navegação principal inclui **Entenda os cargos**.
Filtros GET: `esfera=municipal|estadual|federal|distrital|todos`.
O serviço `service.civic_education` renderiza HTML/CSS, sem JavaScript, banco ou
coleta durante a requisição. Usa o layout e as proteções do portal existente.

O acesso **Entenda os cargos** fica no header, no menu geral com estilo de abas.
As abas internas da pessoa continuam sendo apenas Perfil e Atuação no cargo.

### Diagramas de círculos

Três SVGs acessíveis e locais separam relações diferentes:

- Cargos por esfera: prefeito/vereadores, governador/deputados estaduais e
  presidente/deputados federais/senadores. Círculos separados, sem chefia entre eles.
- Intersecção de responsabilidades: União/estado/município e saúde como exemplo
  de competência comum. Não implica tarefas ou financiamento idênticos.
- Decisões sobre um projeto municipal: prefeito pode propor, vereadores também
  podem propor e votam, projeto aprovado segue ao prefeito para sanção/veto.
  Apresentação, votação e sanção são atos distintos; há iniciativas reservadas.

Os SVGs têm títulos/descrições para leitores de tela, legendas junto aos desenhos
e estilos externos. O tema é atuação de cargos, não hierarquia de lugares.
Fontes: Constituição e explicação oficial da Câmara de São Paulo sobre leis.

O segundo cartão inclui um exemplo concreto de UBS: manutenção/equipes/atendimento
na gestão municipal; apoio financeiro e organização regional pelo estado; políticas
e cofinanciamento federais. A reforma de uma sala e o encaminhamento a especialistas
são problemas diferentes. O exemplo não afirma repasse automático, divisão em terços,
execução conjunta de toda obra ou situação real de uma UBS identificada. Há orientação
sobre cobrança da gestão, fiscalização pelos vereadores e acompanhamento social.
Fontes vinculadas: Ministério da Saúde, Gestão dos Entes do SUS, financiamento da
atenção primária e Requalifica UBS, consultados em 18/10/2026.

## Conteúdo e limites

O desenho separa esferas autônomas e funções dos Poderes. A Presidência é a chefia
do Executivo federal, sem criar uma cadeia de chefia sobre governadores,
prefeitos, Legislativo ou Judiciário. As conexões são rotuladas como relações
de leis, orçamento e fiscalização. Hierarquia administrativa dentro do Executivo
é explicada separadamente.

Cada cargo tem três frases introdutórias: faz, não faz, de quem precisa. A
camada detalhada oferece fundamento e fonte. O DF tem explicação própria.
Os cartões também respondem explicitamente se o cargo pode apresentar propostas,
se vota no Legislativo ou decide sanção/veto no Executivo, e quem pode ser
atendido ou afetado. Os órgãos são acompanhados das pessoas que os integram:
vereadores na Câmara Municipal, deputados estaduais na Assembleia, deputados
federais na Câmara e senadores no Senado. O alcance de uma lei não é confundido
com a região em que o parlamentar recebeu votos ou com benefício garantido.
Leis ordinárias/complementares, PEC, MP, lei delegada, decreto legislativo e
resolução têm rotas distintas. Também há Constituição estadual, Lei Orgânica
municipal/DF, orçamento, decretos e atos administrativos. A iniciativa popular
é forma de apresentação, não nova espécie normativa. O guia não presume que
todos os municípios ou estados tenham os mesmos procedimentos.

Fontes oficiais ficam vinculadas nos próprios cartões. Fontes consultadas em
18/10/2026 incluem Constituição compilada, Câmara dos Deputados, Senado, TSE,
ALESP, ALERJ, Câmara de São Paulo e CLDF. Conteúdo educacional versionado no
repositório; não é gerado a partir de frequência de votos de uma pessoa.

## Evidência sobre aprendizagem

As decisões são hipóteses de aplicação de estudos, não prova de eficácia desta
interface nem certificação neurocientífica.

- **Sinalização:** rótulos junto aos desenhos e consistência das relações.
  [Richter, Scheiter e Eitel, 2016](https://doi.org/10.1016/j.edurev.2015.12.003)
  encontraram benefício médio pequeno a moderado em compreensão/transferência,
  com diferenças entre públicos. A evidência não determina uma paleta específica.
- **Partes controladas pela pessoa:** escolha de esfera e detalhes recolhidos.
  [Rey e colegas, 2019](https://doi.org/10.1007/s10648-018-9456-4)
  sintetizam evidências de segmentação, em muitos casos com maior tempo de estudo.
  A transferência para cartões de texto desta página é uma decisão de projeto.
- **Recuperação ativa com resposta:** perguntas concretas e respostas sob demanda.
  [Dunlosky e colegas, 2013](https://www.psychologicalscience.org/journals/pspi/1529100612453266/)
  revisam evidências de prática de testes. O simples ato de abrir uma resposta
  não comprova que houve recuperação ativa ou aprendizagem.
- **Neurociência complementar:**
  [Wing, Marsh e Cabeza, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3932674/)
  investigam correlatos neurais do efeito de recuperação com fMRI em tarefa de
  memória. Isso não mede a compreensão de cargos por crianças nesta interface.
- **Limites e resultados mistos:**
  [metanálise de 2025 sobre estudos de Mayer](https://www.sciencedirect.com/science/article/abs/pii/S1747938X25000673)
  relata variação entre princípios, com alguns efeitos médios não significativos
  na amostra analisada. Não usar “cientificamente comprovado” como selo da página.

Não foram usados supostos estilos de aprendizagem, hemisfério dominante,
animação decorativa, “cores que ativam o cérebro” ou limite mágico de elementos.

## Validação ainda necessária com o público

A linguagem introdutória foi escrita para leigos, sem afirmar adequação etária
medida. Para validar com crianças de 10 anos e adultos sem conhecimento prévio,
observar, com consentimento apropriado, tarefas como:

1. Encontrar quem executa uma obra municipal e quem fiscaliza.
2. Explicar se um prefeito recebe ordens do governador.
3. Identificar quem vota um projeto federal e o que faz o presidente.
4. Distinguir uma lei ordinária de uma emenda constitucional quanto à sanção.
5. Localizar uma fonte sem precisar ler todos os detalhes jurídicos.

Registrar respostas, erros de interpretação, tempo de localização e necessidade
de ajuda. Não inventar taxa de compreensão. Rever textos e conexões que produzam
confusão. A inspeção visual/responsiva e os testes técnicos não substituem esse
estudo com pessoas.

Complexidade: consulta de esfera O(1) médio; renderização O(c + t), para cargos e
tipos normativos apresentados. Memória proporcional ao HTML produzido. Sem N+1
remoto e sem alterações nas tabelas canônicas para servir conteúdo educativo.

O card “Quem propõe e quem vota?” apresenta as quatro esferas, com vereadores,
deputados estaduais, distritais e federais, senadores, prefeitos, governadores e
presidente. Separa proposta, voto e sanção/veto; explica vices, suplentes, iniciativa
reservada, participação popular e a exceção das PECs (CF, arts. 60 a 66).

## Exemplos concretos de saúde por cargo

Os 13 cards agora mostram um impacto concreto na saúde e detalhes opcionais
sobre unidades, equipamentos, manutenção, profissionais, salários, verba e
resposta a problemas. A gestão da unidade é distinguida da origem do recurso.
UPA e hospital não são presumidos municipais. Salários de servidores dependem
de lei, iniciativa competente, orçamento e limites legais. Vices e suplentes
têm exemplos que respeitam suas atribuições e a necessidade de assumir o cargo.
Não são realizações verificadas de pessoas específicas. Fontes: Lei 8.080/1990,
arts. 9º e 16 a 18; Constituição, arts. 37, 61, 165 a 169 e 198; página oficial
do Ministério da Saúde sobre UPA. Revisão em 18/10/2026. O pacote estático deve
ser reconstruído após cada alteração de conteúdo.

Cada card identifica logo abaixo do título o poder (Executivo ou Legislativo),
a instituição de atuação e a esfera. Prefeitos e governadores governam com
secretarias; presidente governa com ministérios. Secretarias não são casas
legislativas. Vices não são secretários ou ministros automaticamente. Suplentes
só exercem o mandato ao assumir.

O card 2 foi resumido em dois exemplos: mudança de regra nacional do SUS
por lei (Executivo e Legislativo) e reforma de UBS municipal (prefeitura
executa; vereadores votam orçamento e fiscalizam). O diagrama agora distingue
os poderes, em vez de esferas de governo. Não pressupõe nova lei para cada reparo.

Os dez tipos principais têm exemplos práticos e links específicos para fontes
oficiais. Propostas e atos históricos são identificados. A PEC 8/2025 é apresentada
como proposta relacionada ao debate da escala 6×1, com o arquivamento registrado
na ficha consultada em 18/10/2026, sem inferir vigência de uma mudança constitucional.
A EC 90/2015 é o exemplo de emenda promulgada. Orçamento traz situação ilustrativa
explicitamente identificada; decreto e portaria têm exemplos reais do SUS.
