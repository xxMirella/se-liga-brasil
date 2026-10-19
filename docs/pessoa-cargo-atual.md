# Cargo público atual na pessoa

Implementação em 17/10/2026 (America/Belem), migrações 0013 e 0014. A tabela principal continua sendo `se_liga_brasil.person`, identificada pelo UUID interno permanente.

## Campos

- `has_current_public_office`: booleano anulável. `true` confirma exercício atual; `false` exige evidência administrativa verificada de ausência de cargo público em escopo global; `NULL` significa desconhecido.
- `current_public_office_kind`: tipo do cargo confirmado, por exemplo `federal_deputy`, `state_deputy` ou `senator`.
- `current_public_office_institution_id`: FK para o órgão.
- `current_public_office_term_id`: FK opcional para o mandato conhecido. Pode ser nulo quando a fonte confirma exercício atual, mas não permite identificar com segurança o período do mandato.
- `public_office_status_as_of`: data da avaliação do retrato atual, não data de posse.
- `public_office_status_source_record_id`: evidência do estado confirmado.

Esses campos são um retrato derivado. Histórico e evidências continuam em `office_term`, `office_exercise` e `person_fact`; não são substituídos pela flag. Quando existem vários cargos confirmados, o retrato escolhe a evidência mais recente; os demais vínculos permanecem no histórico.

## Regras de segurança factual

A candidatura, mesmo com resultado eleitoral, não estabelece exercício atual. Pagamento, ausência em folha e fim do mandato em uma casa também não comprovam ausência de todo cargo público.

O retrato aceita exercício com período válido e evidência recente, ou observação institucional explícita atual. As observações usam `person_fact.field_name=current_public_office_observation`, `administrative`, `verified`, com `inExercise`, `observedOn`, `officeKind` e `institutionCode`. A atualização em lote é restrita às pessoas do artefato; avaliações de completude atualizam o conjunto. Evidências com mais de 30 dias precisam de atualização antes de sustentar o estado atual. Datas de observação não viram datas individuais de posse.

Uma observação `inExercise=false` exclui somente aquele órgão e não produz flag global falsa. Para `false`, o contrato exige fato `public_office_status`, administrativo/verificado, `hasCurrentPublicOffice=false`, `scope=all_public_offices` e intervalo explícito `validFrom`/`validUntil` vigente, com evidência recente. Se houver evidências atuais contraditórias de exercício e ausência global, o retrato permanece desconhecido. Não há fonte universal validada que permita preencher automaticamente `false` para todos os demais candidatos.

Com ausência global comprovada, completude considera o cargo respondido e salário desse cargo `not_applicable`; não grava salário zero nem apaga pagamentos anteriores. Aposentadoria e pensão são outros vínculos, não esse campo salarial.

## Orquestração integrada

Rotas consideram campo e órgão confirmado; na falta dele, cargo e UF da candidatura servem apenas como pista de descoberta. RJ estadual vai para ALERJ, SP estadual para ALESP e Senado possui rota própria. A fila existente é corrigida, sem criar pessoas novas.

TSE recebe os campos pessoais e bens solicitados; ALESP executa folha somente quando salário é solicitado. ALERJ e Senado expõem as capacidades realmente implementadas. Campos ainda não suportados são bloqueados com motivo, sem marcar processamento concluído ou repetir HTTP. Fonte FILIA permanece bloqueada até validação de recurso nominal.

Se a Câmara não confirmar correspondência no roster, a tarefa de cargo/salário/atividade fica bloqueada por identificação ou exercício não confirmado; partido segue para validação de filiação. Isso não altera a flag para falsa. A ausência de tarefa pronta não significa completude da base.

## Verificação e operação

Testes PostgreSQL usam pessoas fictícias em schemas isolados e rollback. Foram verificadas idempotência, observação sem data de posse, ausência institucional versus global, expiração, rota por UF e preservação de pendências não atendidas.

O retrato usa operações de conjunto e índices: leitura/projeção de n evidências custa O(n), sem uma consulta remota por pessoa. IDs das fontes continuam somente como pontes técnicas de extração; a ligação definitiva usa dados pessoais verificados e `person_id`.


## Aplicação real desta entrega

As migrações preservaram as 15.448 pessoas. Foram projetados 89 perfis locais ALESP, com zero HTTP e zero rejeições; somados à referência da Câmara, o retrato confirmou 90 pessoas com cargo atual (89 estaduais e uma federal). Outras 15.358 ficaram desconhecidas, sem flags falsas fabricadas. A completude resolveu e expurgou 178 pendências de cargo/partido; restam 63.096 linhas abertas nesta fotografia.

As autorias ALESP foram analisadas localmente, mas não ingeridas em massa nesta execução. Os novos coletores ALERJ/Senado tiveram projeções verificadas em schemas de teste com rollback; não se afirma que todo o backlog foi coletado.


Em execução posterior pelo orquestrador, os perfis de duas pessoas da Câmara e uma referência no Senado ampliaram os cargos confirmados para 93. Uma referência ALERJ teve pagamento e partido materializados, mas exercício atual permaneceu desconhecido porque o contrato implementado ainda não confirma esse campo. A pista de eleição anterior orienta pesquisa; somente a evidência institucional permite a flag verdadeira.
