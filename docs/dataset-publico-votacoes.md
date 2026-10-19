# Dataset público simples de votações

Uma linha representa o voto ou estado de participação de uma pessoa em uma votação específica. `person_id` é o UUID interno; `voting_id` separa votações, turnos e objetos da mesma matéria. Não há um arquivo por pessoa, nem uma linha única por lei.

O contrato `person_voting_timeline.v1` apresenta instituição, data e precisão, tipo/número/ano/nome da matéria, descrição curta, link oficial, objeto votado, turno, escolha e participação. Campos de estado distinguem informação desconhecida. Proposta ou PEC não recebe o rótulo de lei promulgada apenas por ter sido votada.

A descrição vem de texto oficial ou curadoria explicitamente identificada. O limite visual é 280 caracteres. Quando uma ementa excede esse tamanho, o resultado é marcado como trecho oficial, não como resumo interpretativo. Quando não há texto comprovado, a descrição fica nula. Um processo técnico ou o título da votação não substitui uma explicação da matéria.

O vínculo pessoal e a evidência são validados antes da publicação. O Parquet público não contém hashes privados de identidade, documentos, IDs pessoais dos provedores ou payloads originais. Votos a favor/contra, abstenção, obstrução e estados de ausência/presidência/não registrado continuam distintos. O objeto votado impede apresentar voto sobre emenda/destaque como posicionamento sobre a matéria integral.

## Operação local

`se-liga-brasil build-voting-timeline --source senado --years 2026 --env-file CAMINHO_ENV` exporta fatos canônicos em lotes e publica uma partição Parquet validada, separada de `person_votes.v1`. `--dataset-directory` altera o destino e `--input-file` aceita NDJSON estritamente no contrato. O primeiro exportador ainda lê tabelas existentes: não migra nem apaga o histórico PostgreSQL.

O frontend deve consumir a API paginada sobre o dataset publicado. O adaptador HTTP atual ainda lê tabelas; a troca para leitura desse novo dataset é uma integração pendente. Publicar o Parquet por si só não altera a API.

## Hospedagem sem cartão

A escolha atual é Supabase Storage no projeto existente. O pipeline diário e o bucket privado estão descritos em `docs/pipeline-votacoes-agendamento.md`. A publicação real de uma partição do Senado foi validada, com ementa oficial e hashes conferidos. O dataset anual continua disponível como exportação separada; o worker publica por ano/mês/dia.

O Hugging Face Datasets permanece alternativa de hospedagem versionada, sem contratar compute ou plano pago; armazenamento público gratuito é best-effort e tem limites. Não foi criada conta nem feita publicação no Hub.

Referências:
- https://supabase.com/pricing
- https://supabase.com/docs/guides/storage/buckets/fundamentals
- https://huggingface.co/docs/hub/storage-limits
- https://huggingface.co/docs/hub/rate-limits
