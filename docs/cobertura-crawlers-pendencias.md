# Cobertura dos crawlers e da fila de completude

Auditoria em 17/10/2026 (America/Belem). Consultas agregadas somente leitura na base real; nenhum dispatch global ou nova ingestão foi executado. Resultado agregado em `data/private/crawler-coverage-audit.json`. Arquivos originais preservados.

## Prontidão

A infraestrutura de delegação existe: fila persistente idempotente, reserva com lease/SKIP LOCKED, lotes, agrupamento fonte/pessoa, cache, limites e cooldown persistente, reavaliação e expurgo. Isso não significa cobertura funcional de todas as pendências. Não há agendamento instalado. O roteamento atual usa o cargo da candidatura mais recente, sem UF nem confirmação de exercício atual.

Problemas verificados no código:

- `route_data_gaps` manda cargo 7 para ALESP inclusive RJ: 4.481 pessoas com candidatura estadual RJ estão no grupo errado. Cargo 7 SP soma 4.773 pessoas. São candidatos históricos, não contagens de deputados em exercício.
- Senado (cargo 5) não tem conector/rota: 71 pessoas, 284 pendências de partido/cargo/salário/atividade bloqueadas sem fonte. Seus bens, quando ausentes, podem continuar atribuídos ao TSE.
- Nascimento e escolaridade são atribuídos ao TSE, mas `collect_requested_source` chama somente o backfill de bens. Essas tarefas não são atendidas pelo dispatch atual.
- ALESP executa folha/identidade e salva relatórios partidários em `person_fact`; ainda não projeta esses relatórios em `political_party_affiliation` nem exercício em `office_term`/`office_exercise`. A completude consulta justamente essas tabelas. Disponibilidade local não equivale a campo atendido.
- ALESP anuncia capacidades legislativas em constante de código, mas o escopo executável aceita apenas `deputy_payroll`. Não há ingestão das proposituras locais.
- Os 31 conflitos patrimoniais são encaminhados ao TSE, porém a seleção de backfill exclui `reported_no_assets` e anos com bens já ingeridos: é necessário reconciliar evidências, não repetir download.
- Câmara está operacional para parlamentares atuais identificáveis com segurança. O roster atual não cobre todos os candidatos históricos; ausência não comprova inexistência de cargo, partido ou patrimônio. O caminho carrega perfil, salário e proposituras juntos, mesmo quando somente um domínio falta.

## Pendências observadas

63.274 linhas abertas, 15.447 pessoas; nenhuma dessas linhas foi tentada pelo novo dispatch na fotografia da auditoria. Enriquecimentos anteriores podem existir e não são contabilizados como tentativas da fila recém-criada.

- Partido atual: 15.447.
- Cargo atual: 15.447.
- Salário atual: 15.447 (100 desatualizados, 15.347 sem pagamento verificado).
- Atividade legislativa: 15.447.
- Declaração de bens: 741 (710 ausências e 31 conflitos).
- Patrimônio declarado: 741, referentes às mesmas pessoas e à mesma declaração acima; não são 741 novas pesquisas independentes.
- Nascimento: 2; escolaridade: 2. Nome completo não tem pendências.

O número bruto superestima trabalho de coleta: candidatura não prova eleição, exercício ou recebimento. Devemos suportar não aplicável com evidência, não publicado ainda, revisão de identidade, conflito e fonte indisponível. Ausência isolada não pode produzir zero salarial, encerramento de mandato ou desfiliação. Atividade legislativa ausente não prova inatividade política. A atual fila nem sequer avalia aposentadoria, pensão ou datas de filiação; criar crawlers desses domínios exige ampliar regras/tarefas.

## Aproveitamento e ordem de implementação

1. Corrigir roteamento para campo + órgão + UF + vigência/exercício; rotas devem refletir capacidades executáveis. Registrar consultas negativas verificadas e impedir repetição indefinida de fontes inadequadas. Reprocessar atribuições existentes após corrigir a regra (não basta mudar casos ainda sem fonte).
2. Ampliar TSE: reaproveitar os arquivos de candidaturas para nascimento/escolaridade e resultados eleitorais como evidência de eleição, sem converter eleição futura em exercício atual. Reaproveitar arquivos de bens por eleição/UF; analisar 31 conflitos individualmente por evidências e republicações. DivulgaCandContas é complemento oficial seletivo, com contrato operacional a validar.
3. Ampliar ALESP, sem criar outro crawler da mesma instituição: projetar perfis, exercício e partido já coletados, preservando datas explícitas; ingerir proposituras/autoria e depois tramitação/votos. Já existem localmente 278.014 proposituras e 1.119.878 relações de autoria, além de outros XML/ZIP: começar pelo disco, validar o cruzamento técnico entre autores e perfis antes de ligar ao `person_id`. Não modificar originais. Campos de autoria não comprovam aprovação de lei ou impacto.
4. Criar `crawlers/alerj`: deputados/perfis/mandatos/partido, remuneração e atividade legislativa. O portal oficial lista folhas mensais PDF, inclusive setembro/2026; estrutura das linhas e ligação pessoal precisam de amostra validada. Preferir lotes por competência; não prometer associação automática por nome isolado.
5. Criar `crawlers/senado`: senadores, exercício/mandatos/partido, remuneração e atividade legislativa. O portal oficial tem transparência de senadores e dados abertos; validar cada recurso, escopo e chave antes de ingestão.
6. Extensão de filiação TSE/FILIA: necessária para candidatos sem mandato e histórico partidário além das casas legislativas. O catálogo de perfil de filiação não comprova histórico nominal completo. O antigo link da relação de filiados redirecionou à página inicial nesta auditoria. Validar acesso público atual e layout antes de prometer crawler ou cobertura universal. Relatórios institucionais com datas explícitas são o primeiro caminho mais barato para os parlamentares já coletados. Data de observação não é data jurídica de entrada/saída; preservar SCD2 e proveniência.
7. Complemento previdenciário/administrativo: criar conectores de Transparência SP e GESPERJ/ConectaRP RJ conforme `fontes-previdenciarias.md`, e atos DOE/DOERJ seletivos para datas/fundamentos. Esses conectores cobrem vínculos adicionais, não substituem folhas legislativas. RJ ainda precisa validar layout/exportação; CPF mascarado não resolve identidade sozinho. Executivo federal só quando houver vínculo pertinente. Portais municipais só se pessoas identificadas exigirem esse escopo; o cargo da última candidatura não descobre todos os empregos atuais.

## Custo e chamadas

Primeiro usar arquivos existentes; depois atualizar catálogo uma vez por fonte/competência, baixar cada artefato uma vez e atender várias pessoas/campos com ele. Separar refresh por domínio na Câmara, para salário mensal não recarregar toda a produção legislativa. Distinguir competência ainda não publicada de falha de ingestão: as 100 remunerações desatualizadas não comprovam 100 falhas do crawler. Agrupamento é O(t) em tarefas e memória O(t); leitura de n registros é O(n), não O(1). Índices pessoais permitem lookup médio O(1) em memória, com processamento em lotes/streaming e índices PostgreSQL.

## Fontes oficiais consultadas

- Câmara, documentação: https://dadosabertos.camara.leg.br/swagger/api.html
- ALESP, processo legislativo: https://www.al.sp.gov.br/dados-abertos/grupo/1
- ALERJ, folhas mensais: https://transparencia.alerj.rj.gov.br/section/report/73
- Senado, senadores: https://www12.senado.leg.br/transparencia/sen/senadores
- Senado, dados abertos: https://www12.senado.leg.br/dados-abertos/administrativo/senadores
- TSE, catálogo de partidos: https://dadosabertos.tse.jus.br/dataset/delegados-partidarios
- TSE, portal/DivulgaCandContas: https://www.tse.jus.br/

Esta auditoria identifica trabalho necessário; não implementa novos crawlers nem afirma que todos os dados desejados estejam disponíveis publicamente.
