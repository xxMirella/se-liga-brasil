# Cobertura histórica e delegação

O serviço de completude combina campos mínimos com cobertura por pessoa, instituição, domínio e período. Ter uma proposição não comprova histórico completo. A tabela privada `person_career_coverage_receipt`, criada pela migração 0018, registra verificações idempotentes por escopo, data, hash do arquivo, versão do parser e evidências de identidade, enumeração e período.

O comando `enrich --include-career` ativa a delegação adicional de atividade histórica. A execução usa as pendências adquiridas pelo trabalhador, agrupa escopos em recursos compartilhados e limita as tentativas. Os bloqueios e períodos de espera da fonte continuam válidos. O registro atual de coletores atende votos do plenário do Senado. Comissões, leis e demais canais sem implementação permanecem pendentes, sem requisições fictícias ou comprovação de completude.

Os escopos legislativos são mensais. No Senado, `plenary/YYYY-MM` e `committee/YYYY-MM` são independentes: consultar o plenário não encerra uma pendência de comissão. Recibos de outro escopo ou duplicados na mesma resposta são rejeitados. Recibos futuros ou sem comprovação suficiente não encerram a cobertura.

`collect-history --source camara --limit 25` enriquece proposições já conhecidas, incluindo tramitações e eventos disponíveis. Não enumera por si só toda a carreira de cada pessoa. `collect-history --source cmsp --years YYYY` usa arquivos anuais, com vínculos de autoria revisados quando fornecidos em `--reviewed-identities`. Esses comandos delimitados não substituem os coletores ainda ausentes.

## Consulta pública de todo o histórico publicado

A aba de atuação usa `get_person_storage_history` em `service/public_profile/storage_history.py`. Essa consulta considera todas as datas publicadas no bucket privado `voting-datasets`, inclusive períodos antigos; a paginação limita a quantidade de resultados por resposta, sem impor uma janela padrão de 30 dias. O filtro manual de período continua usando a consulta diária delimitada, que admite até 31 dias por solicitação.

A descoberta faz uma listagem recursiva paginada do prefixo `legislative/` pelo endpoint Storage `object/list-v2`, com `with_delimiter=false`. O catálogo local tem validade de cinco minutos. Apenas caminhos exatos de manifests de Câmara e Senado viram partições consultáveis. A implementação não tenta consultar cada dia do calendário e não baixa checkpoints privados. O protocolo foi conferido na [referência oficial de listV2](https://supabase.com/docs/reference/javascript/file-buckets-listv2) e no [endpoint oficial do Storage](https://github.com/supabase/storage/blob/master/src/http/routes/object/listObjectsV2.ts).

A listagem admite até 100 páginas de 1.000 objetos; ultrapassar esse orçamento gera `DATASET_CATALOG_BUDGET_EXCEEDED`, sem apresentar um catálogo incompleto como completo. Em cada página do perfil, o serviço examina até quatro lotes de quatro dias efetivamente publicados, mantendo fontes do mesmo dia juntas. Os Parquets passam pelas mesmas verificações de hash, schema e partição da API delimitada. Os filtros por pessoa e exercício são parametrizados no DuckDB. Um próximo cursor permanece disponível quando o orçamento de exame acaba, inclusive em uma página sem voto vinculado; isso não comprova ausência no restante do histórico.

O cursor de histórico é distinto do cursor de período. Ele fixa o catálogo e o contexto de exercício por até uma hora e mantém a ordem por data e identificador da votação. A projeção informa `catalog_pinned=true` e `generation_pinned=false`: os manifests são lidos sob demanda e podem receber correções entre páginas. Não há promessa de uma única geração imutável de toda a carreira. O cache segue o orçamento de 256 MiB do leitor existente. As credenciais permanecem exclusivamente no servidor.

A resposta mantém `full_career_verified=false`, informa a primeira data publicada e diferencia catálogo vazio de ausência de votos vinculados. Ter todas as datas disponíveis no Storage na consulta não significa que todos os períodos da vida pública foram coletados ou identificados.

A descoberta custa O(o + p log p) para o número de objetos listados e partições encontradas; o cache evita repetir a listagem por pessoa durante sua validade. A consulta limita os dias lidos por resposta e filtra os registros dos Parquets examinados. Não é O(1): localizar e produzir eventos exige ler dados, embora os acessos ao catálogo e à deduplicação usem índices em memória.

### Fontes e critérios que continuam pendentes

- Enumeração histórica de proposições da Câmara por pessoa: o coletor atual de tramitação parte de documentos já conhecidos, portanto não prova enumeração completa.
- Votações das comissões do Senado: o coletor existente não fornece ainda uma projeção canônica integrada que encerre esses escopos.
- Votações e produção legislativa das assembleias estaduais e câmaras municipais: arquivos anuais de uma fonte municipal e coletores de remuneração não cobrem esses canais.
- Datas anteriores ao primeiro exercício ou candidatura observado: o início da vida pública continua sem comprovação; não gerar mandatos a partir de candidaturas.
- Empresas, parcerias e outras atuações: exigem fontes e vínculos próprios, sem inferência por nome isolado.

Um recorte histórico só pode ser considerado concluído quando existir recibo do mesmo escopo com identidade, enumeração, período, artefato e parser comprovados. Listar arquivos, baixar dados ou encontrar um evento não substitui esses requisitos. Os testes locais cobrem uma partição antiga, paginação, cache, integridade, separação dos checkpoints e continuação de consulta limitada. A validação real desta entrega foi somente leitura; não houve execução de backfill ou alteração de fatos.
