# Auditoria de encerramento: remuneração ALESP e validação numérica TSE

Auditoria de 17/10/2026 sobre os critérios atuais dos cartões [Remuneração ALESP vinculada às pessoas da base](https://trello.com/c/WbTIPOD6) e [Validação numérica TSE e reprocessamento idempotente](https://trello.com/c/cL8TJmYB). Foram feitas consultas agregadas em transação `READ ONLY`, inspeção de código e testes com schema isolado e rollback. Nenhum arquivo original foi alterado; nenhum dado fictício foi inserido em produção.

## Remuneração ALESP

O entregável pode ser encerrado para as competências publicadas e ingeridas. Há 1.039 pagamentos em `person_payroll_payment`, vinculados a 100 pessoas, entre outubro/2025 e agosto/2026. Todos possuem `person_id` e `identity_status='verified'`. A consulta agregada encontrou zero duplicatas por pessoa, competência, cargo e tipo de folha e zero divergências entre bruto menos deduções e líquido.

A consulta `db/queries/person_payments.sql` utiliza somente tabelas e preserva valores nulos para pessoas sem pagamento verificado. O campo legado `tax_amount` representa as deduções agregadas publicadas, sem inferir rubricas ou salário vigente a partir de uma competência antiga.

A identidade é comprovada pelo resolvedor e por evidências revisadas; nome ou partido isolados não bastam. IDs administrativos recicláveis não substituem o `person_id`. Os testes dirigidos verificam ponte de identidade idempotente, correções e versões, publicação antiga, conflito, destinatário ambíguo, checksum adulterado e deduplicação antes da aquisição.

Limite operacional: a descoberta remota já registrou `NO_PUBLISHED_PAYROLL_RESOURCES`. Isso impede atualizar competências ausentes, mas não invalida pagamentos históricos materializados. O cartão delimitado não exige inventar folha de setembro/outubro nem resolver todos os dados políticos. Cache de 24 horas, limites, aquisição e conexão com locks estão descritos em `docs/crawler-alesp.md`.

## Validação numérica TSE

O entregável pode ser encerrado. A normalização brasileira é explícita; mantém precisão decimal e rejeita sintaxe inválida com motivo. Sinal negativo permitido não é confundido com formato inválido. A migração 0007 está refletida nos dados consultados: 56.540 declarações têm `value_quality_status='reported'`, sem valores negativos; duas declarações têm `negative_requires_review`, ambas com valor negativo preservado.

O teste SQL `test_negative_official_asset_is_preserved_for_review` verifica valor negativo, qualidade e reexecução do mesmo artefato sem nova ingestão. `test_reingestion_is_idempotent_and_changes_preserve_versions` verifica pessoas/eventos e preservação de versões. Os testes puros cobrem exemplos anonimizados do incidente, sentinelas por fonte, separadores, precisão, formato inválido e valores fora de faixa.

A marcação de revisão não significa que os negativos estejam semanticamente confirmados como dívida: essa interpretação continua fora do entregável. O texto mais antigo em `docs/tse-numeric-validation.md` descreve a migração como uma etapa futura; esta auditoria registra sua verificação posterior, sem reescrever o diagnóstico original.

## Verificação reproduzível

Regressões selecionadas: `tests/test_numeric_validation.py`, `tests/test_normalization.py`, `tests/test_alesp_crawler.py`, `tests/test_alesp_identity_source.py`, `tests/test_alesp_reviewed_resources.py` e `tests/test_database_integration.py`. A execução dirigida aprovou os 49 testes selecionados em 112,97 segundos, incluindo os testes SQL. Testes SQL usam exclusivamente schemas temporários e rollback. As verificações de integridade comparam SHA256 dos arquivos locais aos manifestos; não modificam os originais nem assumem que correspondem à versão mais recente disponível na fonte.

Foram conferidos 208 artefatos ALESP e 63 artefatos TSE contra seus manifestos: zero arquivos ausentes e zero divergências de SHA256. Essa contagem inclui os artefatos referenciados pelos manifestos, não uma afirmação de cobertura integral de cada fonte.

O encerramento destes dois entregáveis não declara completude global da base, remuneração atual de todas as pessoas nem cobertura integral da trajetória pública. Os cartões de cobertura, coletores legislativos e atualização de fontes permanecem independentes.
