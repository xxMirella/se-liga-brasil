# Revisão de vínculos de remuneração ALESP por nome

O método legado `exact_legal_name_and_electoral_scope` encontrou um único nome civil
no conjunto de candidaturas de SP ao cargo correspondente. Isso não estabelece,
sozinho, identidade pessoal independente. Não prova que os vínculos estejam errados.

A resolução futura retorna `requires_review`, preserva a sugestão de pessoa e enfileira
`PAYROLL_PERSONAL_IDENTITY_REQUIRED` contra os registros originais da folha.
Nenhuma ponte nova é criada. Pontes oficiais e casos revisados continuam aceitos.

## Prévia segura

Executar `python scripts/audit_name_only_payroll.py --env-file CAMINHO_ENV`.
O script abre conexão com transações somente leitura, exibe UUIDs, quantidade de
pagamentos e existência de documentos/perfis independentes, sem imprimir documentos.
Essas evidências disponíveis precisam ser comparadas ao destinatário da folha;
existir CPF no cadastro não basta para identificar quem recebeu o pagamento.

## Reparo existente: requer coordenação antes de executar

1. Conferir os identificadores afetados e eventuais decisões posteriores mais fortes.
   Não revogar vínculo respaldado por evidência independente do destinatário.
2. Enfileirar a revisão com `source_record_id`, UUID sugerido e motivo explícito,
   de forma idempotente na tabela `person_identity_review`.
3. Antes de qualquer desconfirmação, arquivar uma nova decisão em `source_record`
   com hash calculado pela aplicação. O payload deve conter o identificador anterior
   completo, IDs dos pagamentos, valores anteriores de `person_id`, `identity_status`,
   `office_exercise_id`, e IDs/estados dos fatos derivados afetados. Relacionar a decisão
   aos registros originais. Não alterar payload ou hash de evidência já armazenada.
4. Numa transação única com bloqueio da fonte e comparação da ponte atual com a prévia,
   retirar somente a ponte ativa insuficientemente comprovada e colocar os pagamentos
   correspondentes em `person_id=NULL`, `identity_status='pending'`,
   `office_exercise_id=NULL`. Marcar o fato de identidade derivada como pendente.
   Preservar registros de fonte, versões de ingestão e decisão arquivada.
5. Atualizar projeções e reavaliar pendências apenas após commit; ausência de salário
   confirmado não pode aparecer como remuneração zero.

## Restauração

Uma restauração deve usar exclusivamente a decisão arquivada e comparar os estados
atuais com os estados posteriores ao reparo. Havendo decisão mais nova ou ponte para
outra pessoa, interromper para revisão. Caso contrário, restaurar a ponte, os campos
anteriores dos pagamentos e estados dos fatos na mesma transação. Registrar uma nova
decisão de restauração; não apagar a revisão, a revogação ou evidências históricas.

Nenhuma revogação ou desconfirmação em produção foi executada por este diagnóstico.
