# Enriquecimento de ementas oficiais de proposições do Senado

A função `collect_senate_process_details(connection, storage, process_keys, max_processes=1)` acrescenta a descrição oficial de uma proposição já cadastrada. A execução é explícita, deduplica as chaves antes de HTTP e admite no máximo um processo nesta primeira fatia. Chaves desconhecidas e divergência entre tipo, número ou ano interrompem o fluxo; nenhuma proposição fictícia é criada.

A aquisição reutiliza `collect_process_details`, `SenateAcquisition`, arquivos originais imutáveis, cache, orçamento de bytes, bloqueio da fonte, transporte oficial e tratamento de indisponibilidade. `process_staging.py` conserva somente os campos necessários ao resumo e ao vínculo documental. Códigos pessoais presentes na autoria do original não são persistidos no staging.

A ementa publicada em `conteudo.ementa` alimenta `proposition.summary`. O link oficial já existente em `proposition.official_key` é preservado; `proposition.source_record_id` passa a apontar para a evidência da descrição publicada. `source_record`, `ingestion_entity` e suas versões registram origem e mudanças de conteúdo. A data de observação fica na proveniência, fora do hash do conteúdo normalizado, evitando gerar uma nova versão somente porque houve outra consulta.

Releitura idêntica não gera outra versão. Uma descrição retificada atualiza o resumo e conserva a evidência anterior. Uma observação antiga não substitui a projeção vigente. Se a ementa vier ausente, a execução informa `SENATE_PROCESS_SUMMARY_NOT_PUBLISHED`, mantém o resumo comprovado anteriormente e não declara que a lacuna foi sanada. Nenhum status legislativo, lei produzida ou autoria é inferido nesta fatia.

Em 17/10/2026, uma consulta pública limitada ao [processo oficial de referência](https://legis.senado.leg.br/dadosabertos/processo/9056435.json?v=1) confirmou uma ementa com 201 caracteres e artefato de 62.229 bytes. A amostra foi analisada localmente, sem alterar produção. O SHA-256 observado foi `2f569f32119c6cfc0bbd530676ab8a1fff4066023f95c880c66f2a5aa81ba0a3`. O normalizador reproduziu os campos oficiais de tipo, número e ano, sem gerar descrição própria.

Os testes de SQL usam schema isolado e rollback obrigatório. Comprovam preenchimento relacional com proveniência, replay, correção, rejeição de versão antiga e preservação diante de texto ausente. A aplicação e o dataset público devem ler `proposition.summary` das tabelas; os arquivos originais continuam sendo evidência de ingestão, não arquivos abertos por visita ao perfil.

A busca de proposições existentes é feita em uma consulta de lote. Para p processos e c caracteres de conteúdo relevante, o processamento custa O(p+c), com memória limitada pela aquisição e pelo lote. Há uma consulta oficial por processo único quando o cache exige revalidação; nesta etapa p é limitado a 1. A entrega não comprova cobertura de todas as proposições nem histórico completo de atuação.
