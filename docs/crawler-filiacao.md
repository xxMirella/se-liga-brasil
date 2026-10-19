# TSE/FILIA: disponibilidade e contrato de filiação

Verificado em 17/10/2026, America/Belem. Esta frente não executou ingestão nem alterou arquivos originais. Não foi validada uma fonte pública operacional de histórico nominal universal com entrada e saída de partidos.

## O que a fonte oficial publica

A [página atual de filiação do TSE](https://www.tse.jus.br/partidos/filiacao-partidaria/filiacao-partidaria) direciona ao FILIA externo, descrevendo acesso de administradores partidários. Isso não comprova um endpoint público para consulta automatizada de terceiros.

O [catálogo Partidos](https://dadosabertos.tse.jus.br/dataset/delegados-partidarios) lista delegados, órgãos e perfil de filiação. A página do [recurso de perfil](https://dadosabertos.tse.jus.br/dataset/delegados-partidarios/resource/0ca1f730-ab27-471d-b608-6d94a38dd24a) não forneceu layout nominal validado nesta pesquisa. Portanto, esses recursos não são aceitos como histórico pessoal. Estatísticas agregadas não resolvem pendência de uma pessoa.

A [Resolução TSE 23.596, texto consolidado, art. 26](https://www.tse.jus.br/legislacao/codigo-eleitoral/normas-editadas-pelo-tse/resolucao-no-23-596-de-20-de-agosto-de-2019-2013-brasilia-df-1) descreve publicação de relações oficiais durante janela eleitoral e serviço permanente de certidão restrito ao titular. O §2º limita a relação a filiações regulares e exclui histórico de canceladas. Os campos descritos incluem nome, partido, data de filiação, inscrição e localização eleitoral; não incluem CPF/nascimento para associação civil segura. O histórico completo não pode ser prometido a partir dessa relação mesmo que uma exportação venha a ser validada.

A consulta `https://filia-consulta.tse.jus.br/#/principal/menu` não pôde ser recuperada pelo mecanismo de pesquisa (503); isso não prova indisponibilidade universal. Manuais/notícias antigos que anunciam listas não comprovam o funcionamento atual. Nenhuma credencial, certidão de terceiro ou proteção foi contornada.

## Implementação disponível

`src/crawlers/tse_filiation/enrichment.py` expõe `collect_tse_filiation(connection, storage, people, fields=None)`, sendo `people` o agrupamento de UUID interno para campos solicitado pelo orquestrador. Para lote não vazio:

- Retorna `status=blocked`, `requires_source_validation=true` e `PUBLIC_NOMINAL_AFFILIATION_SOURCE_NOT_VALIDATED`.
- Informa zero requisições e zero fatos ingeridos, com uma falha de fonte para o lote inteiro.
- Recomenda cooldown de sete dias. Expirar o cooldown não habilita aquisição: o contrato continua bloqueado até implementação e validação explícitas.
- Não grava fatos, não modifica a pessoa nem marca pendências como processadas. Não cria tabela de histórico de tentativas.

Esse é um limite de disponibilidade implementado, não um crawler nominal operacional. Não há parser ou SQL de projeção fictício. O orquestrador deve manter essas pendências abertas, considerar `blocked` incompleto e evitar tentativas por pessoa. Não é necessário agendamento para descobrir repetidamente a mesma ausência de contrato.

## Caminho para cobertura útil

Primeiro reaproveitar histórias partidárias publicadas pelas casas legislativas, vinculadas a identidade já confirmada. Cada fonte mantém proveniência e escopo próprios; cobertura de parlamentares não cobre toda pessoa candidata. Partido eleitoral é evidência na data da candidatura, não prova de partido atual.

Para habilitar aquisição nominal futura, validar conjuntamente: URL pública oficial, janela/competência e layout real, critérios pessoais suficientes para ligação ao UUID, significado de cada data e cobertura dos registros. Usar uma aquisição por arquivo/versão, originais imutáveis, índices e processamento em lotes. Nome isolado, partido e inscrição eleitoral não substituem resolução civil corroborada.

SCD tipo 2 deve distinguir intervalo observado pelo sistema do intervalo jurídico de filiação. Ausência numa lista não encerra vínculo; novo partido observado não permite inventar data de saída do anterior. Datas jurídicas só são preenchidas quando a fonte as declara explicitamente. Mudanças e correções exigem idempotência e evidências, sem sobrescrever fatos anteriores.

O contrato atual agrega campos em O(t) para t tarefas, com memória O(f) para f campos distintos. Não faz consultas remotas ou de banco por pessoa. A futura leitura de n linhas custará O(n), com lookup pessoal médio O(1) em índice de memória quando aplicável.
