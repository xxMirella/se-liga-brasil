# Evidência de classificação do governo Bolsonaro

O estudo original de Marcelo de Souza Marques e Euzeneia Carlos, publicado em Sociologias em 2025, classifica o discurso do governo Bolsonaro como populismo de extrema direita. A introdução delimita o governo estudado como 2019–2022. Portanto, 2020 está dentro do período documentado, mesmo quando o presidente não tinha filiação partidária. A classificação do governo não depende da classificação do partido.

Fonte primária acadêmica: https://www.scielo.br/j/soc/a/Rdd3xgrqpCF9Cr5QrLNPT8R/?lang=pt — DOI https://doi.org/10.1590/1807-0337/e140107.

O corpus contém 23 documentos: programa eleitoral de 2018, discursos de posse, pronunciamentos em rádio/TV e discursos na ONU, com documentos até 2022. A evidência é uma análise discursiva retrospectiva do período, não quatro medições anuais independentes nem auditoria de cada política. O catálogo preserva separadamente publicação (2025), corpus (2018–2022) e governo estudado (2019–2022).

A interface usa a categoria `far_right`, rótulo “Extrema direita”, preservando a terminologia “populismo de extrema direita” e o escopo `government_discourse`. Essa classificação não é atribuída automaticamente a partidos, parlamentares, aliados ou eleitores. Tampouco se infere equivalência com fascismo ou ditadura.

Identidade da evidência: `br-presidency-jair-bolsonaro-2019-2022`. A função `classify_executive_orientation` exige essa identidade explícita e um ano estudado; não identifica governos por semelhança de nome nem utiliza o rótulo do partido. Outros governos e anos permanecem sem classificação documentada nesta primeira versão.

A proveniência arquiva um excerto curto revisado da fonte primária, com SHA-256 e escopo `reviewed_excerpt_utf8_not_original_document`. O hash comprova o arquivo revisado local, não os bytes originais do artigo. Catálogo e serviço estão em `src/service/political_dashboard/executive_orientation_evidence.{json,py}`. O catálogo de especialistas sobre partidos permanece intacto.

Validação: nove testes específicos cobrem 2019–2022, rejeição de extrapolação para 2018/2023 e identificação por partido/nome, hash do excerto e isolamento de mutações. Somados aos testes de classificação de partidos: 37 aprovados. Ruff e revisão estrutural passaram.

## Regime militar: evidência distinta

Incluída classificação do regime brasileiro de 1964–1985 como “Direita”, em espécie documental separada (`academic_regime_analysis`, escopo `political_regime`). Costa (2024), https://periodicos.ufmg.br/index.php/temporalidades/article/view/46806, analisa as bases conservadoras e a identificação militar com a direita (PDF página11, impressa563). Cunha (2021), https://www.scielo.br/j/bpsr/a/NM7nctR83dYfLXyhgR3KgPn/, estuda a legitimação conservadora do regime. Trata-se de síntese historiográfica explicitada no registro, não rótulo inferido simplesmente da palavra ditadura. As próprias fontes reconhecem diversidade interna.

O Senado, vocabulário controlado16005, delimita início em01/04/1964 e término em15/03/1985: https://adm.senado.leg.br/vcb/vocab/index.php?%2Fregime-militar-1964-1985=&tema=16005. O serviço `classify_regime_orientation('senado-vcb:16005', year)` retorna intervalo diário com término exclusivo, recortado ao ano. Assim, 1964 e1985 são parciais, sem substituir o outro regime vigente na parte restante. A classificação não é aplicada às bancadas parlamentares nem sobrescreve filiações pessoais.

O lookup do governo Bolsonaro também aceita exatamente o identificador de exercício já existente `arquivo-nacional-president:199:2019-01-01`. Quinze testes específicos e28 do survey passaram (43 ao todo), com Ruff, revisão estrutural e diff limpos.

## Governos Lula: mandatos e conciliação separados

Incluída orientação geral “Esquerda” para2003–2010 como `literature_based_editorial_summary`, utilizando o artigo original de Marcelo Sevaybricker Moreira, Dados2023, https://www.scielo.br/j/dados/a/Qpx4fcr5TZxzyBd5sz3xFhR/?lang=pt, em conjunto com Singer2009, https://www.scielo.br/j/nec/a/gLqzRSkjs3C8gFgwCQDNWjK/. Singer descreve mistura de elementos de esquerda e direita, estabilidade e distribuição; portanto, o catálogo explicita conciliação entre classes, coalizão heterogênea e políticas de orientações diferentes. Não representa cada ação do governo como esquerda.

O exercício de origem2003–2010 abrange os dois primeiros mandatos na própria fonte de identidade; o terceiro mandato tem registro independente. Para2023, Sena Júnior, Miguel e Filgueiras, https://www.scielo.br/j/ccrh/a/SbtzYkB8xtPDcmSgpLC9LgN/?lang=pt, sustentam a leitura de esquerda em sentido amplo e documentam concessões sob presidencialismo de coalizão. O estudo examina os primeiros seis meses: esta primeira versão não o extrapola silenciosamente para2024–2026 nem afirma medição do ano inteiro. A distinção aparece no escopo e nas limitações.

A classificação dos governos permanece independente da classificação do PT e não muda partidos, filiações ou composição legislativa. Validação ampliada:20 testes específicos e28 do survey,48 aprovados; Ruff, revisão estrutural e diff limpos.

### Decisão editorial explícita para o governo em curso

Em27/10/2026, a usuária autorizou classificar o terceiro governo Lula de modo geral como esquerda, preservando a conciliação entre classes. O catálogo mantém o registro acadêmico de2023 e acrescenta registro separado para2024–2026: `editorial_government_classification`, status `editorial_mandate_summary`, referência editorial2026-10-27. A fonte CRH permanece datada de2023 e identificada como estudo dos primeiros seis meses; não se afirma que mediu2024–2026. O qualificador público informa: “Classificação geral do governo; coalizão e políticas de orientações distintas. Síntese editorial, não medição anual.” Nenhum ano2027 foi incluído. Teste de unicidade impede registros concorrentes para o mesmo exercício/ano. Validação final:52 testes aprovados, Ruff e revisão estrutural limpos.
