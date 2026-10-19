# Identidade interna e validação de observações

`person.id` é o UUID permanente da pessoa, usado pelas relações do sistema. Os arquivos baixados são preservados. IDs externos podem relacionar linhas dos arquivos e eventos de uma mesma fonte; não constituem identidade pessoal.

A resolução TSE prioriza CPF validado, armazenado como fingerprint HMAC privado. Sem CPF válido, consulta nome completo normalizado e nascimento completo. Correspondência única pode reutilizar uma pessoa; múltiplas pessoas compatíveis ou evidência insuficiente geram rejeição/pendência auditável. Partido não pertence à chave. RG não está coberto pelo contrato atual: só deve ser usado com UF e emissor quando uma fonte efetivamente os fornecer.

A migração 0008 remove `candidate:ano` e `public_office_member` do cadastro de identificadores, preserva todos os UUIDs e relacionamentos e muda slugs `tse-*` para `person-<UUID>`. `payroll_recipient` é uma chave derivada internamente do nome publicado e permanece como ponte de uma identidade previamente resolvida; não substitui o UUID. A consulta de exceções revisadas ALESP usa nome/nascimento e contexto eleitoral, sem localizar a pessoa por código de candidatura.

Códigos ainda existem nos dados técnicos de candidaturas, declarações e proveniência para cruzar os arquivos de origem; não são usados para decidir quem é a pessoa. A remoção não funde automaticamente pessoas antigas com dados ambíguos. Reprocessar um evento cuja evidência pessoal indique outro UUID gera revisão, sem trocar o dono silenciosamente.

## Partido político

O verificador reutilizável compara observações mensais pelo UUID. PT em outubro e PL em novembro dispara consulta aos relatos oficiais datados já coletados. Uma entrada no novo partido dentro do intervalo confirma uma mudança **reportada pela fonte**; sem evidência, fica pendente. A comparação usa a precisão mensal da folha, não inventa um dia de mudança. Uma declaração eleitoral antiga não prova filiação atual.

Os perfis ALESP fornecem `listaFiliacoes`, `dtInicio` e `dtFim`; os relatos são guardados como fatos com evidências e versões idempotentes. A convenção inclusiva/exclusiva de `dtFim` não está documentada nos arquivos examinados: preservamos a data reportada sem fabricar um limite de validade. A folha de deputados atual não informa partido, portanto o resultado correto do verificador é `source_does_not_report_political_party`, nunca inventar partido retrospectivamente a partir do perfil atual.

## Aposentadoria, pensão e exercício

A inspeção dos 290 CSVs TSE baixados encontrou `CD_OCUPACAO`/`DS_OCUPACAO` e as descrições `APOSENTADO (EXCETO SERVIDOR PÚBLICO)` e `SERVIDOR PÚBLICO CIVIL APOSENTADO`. São declarações da eleição, não comprovação atual de benefício. Não foi encontrado campo previdenciário específico para pensionista ou ativo. O normalizador atual ainda não projeta ocupação como campo próprio; os valores permanecem nos arquivos originais. Auditoria: `data/tse/employment-status-audit.json`.

No XML ALESP de deputados, o dicionário oficial define `EXE` como no exercício do mandato; também existem `LIC`, `REN`, `REL`, `CAS`, `FAL` e `OUT`. Isso descreve mandato, não situação previdenciária. A API contém `isEmExercicio`. A folha de deputados ingerida tem nome, bruto, tributos e líquido, sem classificação ativo/aposentado/pensionista.

O histórico `182_funcionarios_cargos.xml` contém também `NomeCargo=APOSENTADO`, com datas de início/fim quando disponíveis. É evidência administrativa histórica que precisa ser vinculada à pessoa e interpretada no período; não comprova sozinha benefício atual. Os XMLs de cargos e lotações de servidores têm regimes e datas de início/fim, mas não são uma folha previdenciária individual. Ausência na lotação ou fim de cargo não comprova aposentadoria. Para confirmar benefício é necessária fonte previdenciária/folha de inativos e pensionistas com evidência de identidade. Estado desconhecido deve permanecer desconhecido; uma pessoa pode exercer mandato e simultaneamente ter benefício, portanto não cabe um único booleano global de ativo.

## Custos e limites

As consultas por dados pessoais usam índices e operações em lotes; não se promete O(1) para ler todos os registros. A comparação mensal ordena observações e relatos históricos e usa índice por pessoa/partido com busca binária por data: custo O(N log N + H log H + N log H), memória O(N + H). Os relatos podem divergir entre fontes ou versões: confirmação significa que foi encontrada uma ocorrência reportada compatível no intervalo, não arbitragem definitiva da verdade nem substituição automática da filiação atual.

## Verificação aplicada em 17/10/2026

Migração aplicada na base: 15.448 pessoas preservadas, 17 tabelas relacionadas com conteúdo idêntico antes/depois, 25.801 identificadores externos removidos e 300 arquivos originais preservados por hash agregado de conteúdo. Relatório privado: `data/private/internal-identity-migration-audit.json`.

Reexecução ALESP: 1.039 pagamentos continuam verificados, zero pendências e zero novos vínculos. Foram persistidos 194 relatos partidários, e a segunda execução manteve a cobertura. A folha não informa partido e, portanto, não produz comprovação de mudança mensal de partido. Suíte completa: 100 testes, mais o teste isolado específico da migração e a verificação posterior da ponte de pagamentos.

Para fontes de aposentadoria e pensão, consultar `docs/fontes-previdenciarias.md`; a pesquisa não equivale a ingestão desses benefícios.

O parser TSE passou a `tse-python-v5`. Planos de validação antigos precisam ser regenerados com `validate` antes de `ingest`, usando o mesmo escopo; os ZIP originais são reutilizados sem alteração. O smoke test real de 2026/SP/RJ reprocessou 4.577 registros com zero rejeições e zero novas pessoas, em transação com rollback.
