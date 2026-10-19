"""Different lawmaking routes never share a fictitious universal approval step."""

LAW_SOURCES = {
    "federal": (
        "Câmara · como nascem as normas",
        "https://www.camara.leg.br/entenda-o-processo-legislativo/",
    ),
    "state": (
        "ALESP · caminho de um projeto",
        "https://www.al.sp.gov.br/processo-legislativo/sobre/",
    ),
    "rio": ("ALERJ · como funciona", "https://www.alerj.rj.gov.br/Alerj/ComoFunciona"),
    "municipal": (
        "Câmara de São Paulo · como nascem as leis",
        "https://www.saopaulo.sp.leg.br/camaraexplica/como-nascem-as-leis/",
    ),
    "organic": (
        "Câmara de São Paulo · Lei Orgânica",
        "https://www.saopaulo.sp.leg.br/atividade-legislativa/lei-organica-do-municipio/",
    ),
    "district": (
        "Lei Orgânica do DF",
        "https://dflegis.df.gov.br/ato.php?p=lei-org%C3%A2nica-do-distrito-federal",
    ),
    "delegated": (
        "Senado · manual do processo legislativo",
        (
            "https://www2.senado.leg.br/bdsf/bitstream/handle/id/658699/"
            "Manual_processo_legislativo_3.ed.pdf"
        ),
    ),
    "types": (
        "Câmara · tipos de propostas",
        (
            "https://www2.camara.leg.br/transparencia/acesso-a-informacao/"
            "copy_of_perguntas-frequentes/processo-legislativo"
        ),
    ),
    "quorum": (
        "Câmara · maioria absoluta",
        "https://educacaoadistancia.camara.leg.br/clique_regimento/card/175",
    ),
}

# title, explanation, proposer, voter, finalizer, qualification, source
LAW_TYPES = (
    (
        "Lei ordinária",
        (
            "Cria regras para assuntos do dia a dia, como saúde e direitos do consumidor. Por "
            "exemplo, a Lei 8.080/1990 organiza o SUS e define responsabilidades dos governos "
            "na saúde. É usada quando o assunto não exige lei complementar ou mudança na "
            "Constituição."
        ),
        (
            "No país: deputados federais, senadores, comissões de parlamentares e presidente "
            "da República. STF, Tribunais Superiores e procurador-geral da República também "
            "podem propor nos assuntos de sua responsabilidade. Nos estados: deputados "
            "estaduais e governador; nas cidades: vereadores e prefeito; no DF: deputados "
            "distritais e governador. Cidadãos também podem apresentar projetos com as "
            "assinaturas exigidas. A lista completa varia por esfera e assunto."
        ),
        (
            "No país, deputados federais na Câmara e senadores no Senado. Nos estados, "
            "deputados estaduais; nas cidades, vereadores; no DF, deputados distritais. Em "
            "geral, passa com mais votos a favor do que contra, desde que mais da metade dos "
            "integrantes esteja presente; há exceções."
        ),
        (
            "O presidente, governador ou prefeito recebe o projeto aprovado e concorda com ele "
            "(sanciona) ou o rejeita, no todo ou em parte (veta). Depois das etapas exigidas, "
            "a lei é confirmada oficialmente e publicada."
        ),
        (
            "Nem todo autor pode propor qualquer assunto. Por exemplo, reajustes para "
            "servidores do Executivo precisam partir do presidente, governador ou prefeito "
            "responsável por aquela administração, respeitando as regras. Os parlamentares "
            "analisam e votam a proposta."
        ),
        "federal",
    ),
    (
        "Lei complementar",
        (
            "Trata de assuntos para os quais a Constituição exige esse tipo de lei e mais "
            "votos para aprovação. Por exemplo, a Lei Complementar 150/2015 define regras do "
            "emprego doméstico, como registro da jornada e férias."
        ),
        (
            "No país: deputados federais, senadores, comissões de parlamentares e presidente "
            "da República. STF, Tribunais Superiores e procurador-geral da República também "
            "podem propor nos assuntos de sua responsabilidade. Nos estados: deputados "
            "estaduais e governador; nas cidades: vereadores e prefeito; no DF: deputados "
            "distritais e governador. Cidadãos também podem apresentar projetos com as "
            "assinaturas exigidas. A lista completa varia por esfera e assunto."
        ),
        (
            "Deputados federais e senadores, no país; deputados estaduais, nos estados; "
            "vereadores, nas cidades; deputados distritais, no DF. Exige votos a favor de mais "
            "da metade de todos os integrantes da Câmara, Senado ou Assembleia que estiver "
            "votando."
        ),
        (
            "O presidente, governador ou prefeito sanciona ou veta o projeto aprovado. Depois "
            "das etapas exigidas, a lei é confirmada oficialmente e publicada."
        ),
        (
            "Não manda em todas as leis ordinárias: trata de assuntos específicos e exige mais "
            "votos. Nem todo autor pode propor qualquer assunto. Por exemplo, reajustes para "
            "servidores do Executivo precisam partir do presidente, governador ou prefeito "
            "responsável por aquela administração, respeitando as regras. Os parlamentares "
            "analisam e votam a proposta."
        ),
        "federal",
    ),
    (
        "Emenda à Constituição Federal · PEC",
        (
            "Muda uma parte da Constituição. Por exemplo, a Emenda Constitucional 90/2015 "
            "incluiu o transporte entre os direitos sociais. Antes de ser aprovada e "
            "promulgada, a mudança é uma PEC: uma proposta. A PEC 8/2025, do debate sobre a "
            "escala 6×1, propôs quatro dias de trabalho por semana. Sua ficha, consultada em "
            "18/10/2026, registra arquivamento após a votação da proposta principal. Isso não "
            "comprova uma mudança já em vigor."
        ),
        (
            "O presidente da República; um grupo de pelo menos um terço dos deputados federais "
            "ou dos senadores; ou mais da metade das Assembleias Legislativas, cada uma com "
            "apoio da maioria dos deputados presentes."
        ),
        (
            "Deputados federais na Câmara e senadores no Senado. São duas votações em cada "
            "uma, com pelo menos três quintos de todos os integrantes a favor em cada votação."
        ),
        (
            "As Mesas da Câmara e do Senado, formadas pelos parlamentares que dirigem essas "
            "instituições, confirmam oficialmente a emenda (promulgam). O presidente não "
            "sanciona nem veta."
        ),
        (
            "PEC é a proposta; emenda é o texto aprovado e promulgado. Há limites: por "
            "exemplo, uma emenda não pode abolir direitos e garantias individuais. A "
            "Constituição também impede mudanças durante determinadas situações excepcionais, "
            "como intervenção federal."
        ),
        "federal",
    ),
    (
        "Medida provisória · MP",
        (
            "É uma decisão do presidente que já tem força de lei, mas precisa ser analisada "
            "pelo Congresso para continuar valendo. Por exemplo, a MP 1.039/2021 criou o "
            "Auxílio Emergencial de 2021 durante a pandemia. É um caso histórico: essa MP "
            "perdeu eficácia em julho daquele ano."
        ),
        (
            "O presidente da República publica a MP, que começa a valer sem esperar a votação. "
            "Só pode usá-la quando há relevância e urgência, nos assuntos permitidos pela "
            "Constituição; por exemplo, não pode criar regras penais por MP."
        ),
        "Deputados federais na Câmara e senadores no Senado decidem se a MP vira lei.",
        (
            "Se deputados e senadores mantiverem o texto, o presidente da Mesa do Congresso o "
            "promulga. Se mudarem o texto, o projeto vai ao presidente da República para "
            "sanção ou veto."
        ),
        (
            "Em regra, vale por 60 dias, com uma prorrogação de até 60 dias; a contagem para "
            "no recesso do Congresso. Se não for aprovada a tempo, perde eficácia. Este "
            "caminho descreve a MP federal, não uma autorização geral para prefeitos e "
            "governadores."
        ),
        "federal",
    ),
    (
        "Lei delegada",
        (
            "É uma lei que o presidente escreve após receber autorização do Congresso para um "
            "assunto definido. Por exemplo, a Lei Delegada 13/1992 criou pagamentos adicionais "
            "para determinados servidores federais. O presidente precisava respeitar os "
            "limites da autorização."
        ),
        (
            "O presidente da República pede autorização. Deputados federais e senadores, no "
            "Congresso, votam uma resolução que define o assunto e os limites da lei."
        ),
        (
            "Deputados federais e senadores aprovam a autorização. Só votam o texto final se "
            "essa autorização exigir; nesse caso, não podem mudar o texto nessa votação."
        ),
        (
            "O presidente da República escreve e confirma oficialmente a lei dentro da "
            "autorização recebida."
        ),
        (
            "O Congresso não pode delegar qualquer assunto: por exemplo, não pode autorizar o "
            "presidente a criar uma lei complementar por esse caminho. É diferente de uma "
            "medida provisória."
        ),
        "delegated",
    ),
    (
        "Decreto legislativo",
        (
            "É uma decisão sobre assuntos que cabem ao Legislativo, sem sanção do presidente. "
            "Por exemplo, o Decreto Legislativo 6/2020 reconheceu a calamidade da pandemia e "
            "permitiu regras excepcionais para as contas públicas até dezembro de 2020. É um "
            "exemplo histórico."
        ),
        (
            "No Congresso, deputados federais, senadores e comissões de parlamentares, "
            "conforme o assunto. Na Câmara, alguns projetos só podem partir da Mesa, o grupo "
            "de deputados que dirige a instituição, ou de uma comissão específica."
        ),
        (
            "No Congresso, deputados federais e senadores. Nas cidades, vereadores; nos "
            "estados, deputados estaduais; no DF, deputados distritais, dentro das atribuições "
            "de cada instituição."
        ),
        (
            "No Congresso, o presidente do Senado, que preside a Mesa do Congresso, promulga o "
            "decreto. Nas outras esferas, a presidência da respectiva instituição legislativa "
            "faz essa confirmação. Não há sanção nem veto do presidente da República, "
            "governador ou prefeito."
        ),
        (
            "Não é o decreto que o presidente, o governador ou o prefeito usa para "
            "regulamentar uma lei."
        ),
        "types",
    ),
    (
        "Resolução",
        (
            "Define regras de assuntos que a Câmara, o Senado ou o Congresso podem decidir por "
            "conta própria. Por exemplo, a Resolução da Câmara 17/1989 aprovou as regras sobre "
            "como os deputados debatem e votam, sem precisar da sanção do presidente."
        ),
        (
            "Na Câmara, deputados federais, comissões de deputados ou a Mesa, conforme o "
            "assunto. No Senado, senadores e comissões, inclusive a comissão que dirige o "
            "Senado. Nos estados, deputados estaduais; nas cidades, vereadores; no DF, "
            "deputados distritais, seguindo as regras de sua instituição."
        ),
        (
            "Deputados federais, se for uma resolução da Câmara; senadores, se for do Senado. "
            "Resoluções do Congresso envolvem deputados e senadores. Nas outras esferas, votam "
            "os vereadores ou deputados da instituição correspondente."
        ),
        (
            "O presidente da Câmara, do Senado, da Assembleia ou da Câmara Legislativa, "
            "conforme a resolução, faz a promulgação: a confirmação oficial do texto aprovado. "
            "No Congresso, cabe ao presidente da Mesa do Congresso. Não há sanção ou veto do "
            "Executivo."
        ),
        (
            "Alguns assuntos só podem ser propostos pela direção da instituição ou por uma "
            "comissão específica. Por exemplo, mudar regras internas da Câmara não exige "
            "votação dos senadores."
        ),
        "types",
    ),
    (
        "Constituição estadual e suas emendas",
        (
            "É o conjunto de regras fundamentais de um estado; suas mudanças são chamadas de "
            "emendas. Por exemplo, o artigo 219 da Constituição de São Paulo prevê acesso "
            "universal e igualitário aos serviços de saúde, uma base para cobrar políticas de "
            "atendimento no estado."
        ),
        (
            "Deputados estaduais em grupo e governador, conforme a Constituição do estado. Em "
            "São Paulo, também há participação de Câmaras Municipais e de cidadãos com as "
            "assinaturas exigidas. O apoio necessário para apresentar a proposta deve ser "
            "conferido na Constituição de cada estado."
        ),
        (
            "Deputados estaduais votam na Assembleia Legislativa. A Constituição do estado "
            "define quantas votações e quantos votos são necessários."
        ),
        (
            "A Mesa da Assembleia Legislativa, formada pelos deputados que a dirigem, promulga "
            "a emenda. O governador não sanciona nem veta."
        ),
        (
            "As regras para mudar a Constituição de um estado não são automaticamente iguais "
            "às de uma PEC federal. A população participa quando a Constituição estadual prevê "
            "essa possibilidade."
        ),
        "state",
    ),
    (
        "Lei Orgânica municipal e suas emendas",
        (
            "É o conjunto de regras básicas de uma cidade. Por exemplo, a Lei Orgânica de São "
            "Paulo define as funções da Prefeitura e da Câmara Municipal: quem administra os "
            "serviços e quem fiscaliza o governo da cidade. Suas mudanças são chamadas de "
            "emendas."
        ),
        (
            "Vereadores em grupo e prefeito, conforme a Lei Orgânica da cidade. Exemplo de São "
            "Paulo: pelo menos um terço dos vereadores, o prefeito ou cidadãos com assinaturas "
            "de pelo menos 5% dos eleitores podem propor uma emenda."
        ),
        (
            "Vereadores na Câmara Municipal. Para criar a Lei Orgânica, a Constituição Federal "
            "exige duas votações, intervalo mínimo de dez dias e votos a favor de dois terços "
            "dos vereadores. Para alterar o texto, é preciso conferir o procedimento da cidade "
            "e as decisões judiciais aplicáveis."
        ),
        (
            "A Mesa da Câmara Municipal, formada pelos vereadores que a dirigem, promulga a "
            "emenda. O prefeito não sanciona nem veta."
        ),
        (
            "São Paulo é um exemplo, não uma regra para todos os municípios. A Lei Orgânica de "
            "cada cidade informa quem pode propor emendas e como os vereadores devem votá-las."
        ),
        "organic",
    ),
    (
        "Lei Orgânica do DF e suas emendas",
        (
            "É o conjunto de regras básicas do Distrito Federal. Por exemplo, a Lei Orgânica "
            "do DF organiza as funções do governador e dos deputados distritais. O DF reúne "
            "tarefas de estado e de município, mas não tem prefeito de Brasília. Suas mudanças "
            "são chamadas de emendas."
        ),
        (
            "O governador do DF; pelo menos um terço dos deputados distritais; ou cidadãos com "
            "assinaturas de pelo menos 1% dos eleitores do DF, distribuídas em pelo menos três "
            "zonas eleitorais, com o apoio mínimo previsto em cada uma."
        ),
        (
            "Deputados distritais na Câmara Legislativa. O texto original segue a regra da "
            "Constituição Federal. Para emendas, o texto atual da Lei Orgânica prevê duas "
            "votações, com intervalo mínimo de dez dias e três quintos dos deputados a favor."
        ),
        (
            "A Mesa da Câmara Legislativa, formada pelos deputados distritais que a dirigem, "
            "promulga a emenda. O governador do DF não sanciona nem veta."
        ),
        (
            "O DF não tem vereadores. Suas leis comuns são votadas pelos deputados distritais "
            "e podem passar por sanção ou veto do governador; emendas à Lei Orgânica não "
            "passam por essa etapa."
        ),
        "district",
    ),
)

GLOSSARY = (
    (
        "Norma jurídica",
        "Uma regra oficial sobre direitos, deveres ou funcionamento do poder público. "
        "Leis, decretos e resoluções são exemplos; cada tipo tem sua função e suas regras.",
    ),
    ("Propor", "Apresentar uma ideia escrita. Ainda não é uma lei aprovada."),
    (
        "Comissão",
        (
            "Um grupo de parlamentares que examina um assunto. Em certos casos, "
            "pode decidir sem votação no Plenário."
        ),
    ),
    (
        "Votar e aprovar",
        (
            "Parlamentares dão seus votos. A proposta só passa se alcançar a "
            "quantidade de votos exigida."
        ),
    ),
    (
        "Sanção",
        (
            "O presidente, governador ou prefeito concorda com um projeto de lei aprovado. Em "
            "algumas situações, o silêncio no prazo legal também vale como sanção."
        ),
    ),
    (
        "Veto",
        (
            "O presidente, governador ou prefeito rejeita todo ou parte de um projeto, com "
            "justificativa. O Legislativo pode reexaminar essa rejeição."
        ),
    ),
    (
        "Promulgação",
        (
            "É a confirmação oficial de que a lei ou emenda foi criada. Conforme o tipo, "
            "cabe ao presidente, governador, prefeito ou à direção da Câmara, Senado ou "
            "Assembleia. É diferente de votar e de sancionar."
        ),
    ),
    (
        "Publicação e vigência",
        (
            "A norma é divulgada oficialmente. Começa a valer na data ou no prazo "
            "que as regras aplicáveis determinarem."
        ),
    ),
    (
        "Quórum",
        "A quantidade de pessoas ou votos necessária para uma decisão. Não é sempre a mesma.",
    ),
)


LAW_ROUTES = {
    "municipal": (
        "Lei da cidade",
        "Vereadores ou prefeito; a população também pode propor pelas regras locais.",
        "Vereadores analisam e votam na Câmara Municipal.",
        "Prefeito concorda (sanciona) ou veta.",
        "municipal",
    ),
    "estadual": (
        "Lei do estado",
        "Deputados estaduais, comissões de deputados e governador. Cidadãos e chefias "
        "de órgãos como o Tribunal de Justiça e o Ministério Público também têm "
        "iniciativa nos casos previstos pela Constituição estadual.",
        "Deputados estaduais analisam e votam na Assembleia.",
        "Governador concorda (sanciona) ou veta.",
        "state",
    ),
    "federal": (
        "Lei do país",
        (
            "Deputados federais, senadores, comissões e presidente da República. "
            "STF, Tribunais Superiores e procurador-geral da República propõem nos "
            "assuntos de sua responsabilidade. Cidadãos podem apresentar projetos "
            "com as assinaturas exigidas."
        ),
        (
            "Uma Casa analisa e vota; a outra revisa. Em geral, Câmara e Senado "
            "precisam aprovar o mesmo texto."
        ),
        "Presidente concorda (sanciona) ou veta.",
        "federal",
    ),
    "distrital": (
        "Lei do DF",
        "Deputados distritais, comissões e governador do DF. Cidadãos podem propor "
        "com assinaturas; Tribunal de Contas e Defensoria Pública do DF, nos assuntos "
        "que a Lei Orgânica atribui a esses órgãos.",
        "Deputados distritais analisam e votam na Câmara Legislativa.",
        "Governador do DF concorda (sanciona) ou veta.",
        "district",
    ),
}
