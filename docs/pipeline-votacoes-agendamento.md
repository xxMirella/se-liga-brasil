# Pipeline de votações: coleta, alterações e Storage

O agendamento utiliza `pg_cron`, não uma automação Codex nem crontab da máquina. O job `se-liga-brasil-voting-refresh` roda nos dias 1 e 15 às 08:00 de America/Belem (11:00 UTC). O PostgreSQL apenas enfileira tarefas pequenas; o trabalhador Python executa os crawlers oficiais do Senado e da Câmara.

Cada disparo cria tarefas diárias para reconsultar os 45 dias anteriores, excluindo o dia em andamento. A janela sobreposta captura retificações recentes, não certifica retificações anteriores a ela. A fila é idempotente por fonte, data do disparo e dia consultado. Não armazena votos: apenas controle operacional, lease, tentativas, flag `processed` e contagens resumidas. Processados e histórico dos próprios jobs cron são expurgados após sete dias; falhas não são apagadas silenciosamente.

## Ordem de execução

1. O trabalhador adquire uma tarefa com lease e trava por fonte.
2. O crawler consulta o período, reutiliza cache e baixa originais novos/alterados. Os arquivos originais permanecem imutáveis.
3. A leitura valida os fatos e resolve pessoas por nome completo e nascimento únicos com evidência oficial, em lotes. IDs pessoais dos provedores permanecem transitórios. Documentos, perfis e matérias são deduplicados antes das chamadas caras.
4. O detector local compara os fatos com os já processados. Timestamp de revalidação sozinho não é dado novo. Nenhum fato novo/alterado e nenhuma retirada explícita: a consolidação e o upload não são acionados.
5. Havendo alterações, o serviço separa por data e consolida pessoa+votação com o histórico existente. Arquivo parcial/vazio não apaga registros. Retificações exigem observação mais recente; conflito na mesma observação é rejeitado.
6. Parquet público e checkpoint privado são enviados ao bucket privado `voting-datasets`; o manifesto é ativado por último. Somente depois do sucesso o detector confirma o lote. Falha de upload permite retry sem perda ou duplicação.

Retirada nominal só ocorre com evidência explícita, como correção para votação secreta. Tombstones privados impedem que um arquivo antigo restaure votos retirados. Ausência numa resposta não prova ausência na votação nem autorização para apagar votos.

## Partições e conteúdo

`legislative/{instituicao}/person_voting_timeline/year=YYYY/month=MM/day=DD/`

Cada dia contém um Parquet público consolidado com nome derivado do hash, checkpoint privado de revisões, manifesto e histórico local de gerações. O conteúdo público traz person_id interno, identificador técnico da votação, tipo/número/ano/nome da matéria, descrição curta oficial ou curada com estado explícito, link oficial, data/precisão, objeto/turno, escolha e participação. Uma PEC votada não é rotulada automaticamente como lei. O checkpoint privado não deve ser servido ao frontend.

O bucket é privado. A chave de servidor fica em `.env.storage`, ignorada pelo versionamento e restrita ao usuário; não entra no frontend, logs ou documentação. O worker usa credenciais de banco pelo arquivo de ambiente indicado no comando e a configuração de Storage pelo arquivo privado. Arquivos são limitados a 50 MiB por objeto neste adaptador; o repositório derivado aplica orçamento de 256 MiB. A cota de Storage do plano gratuito e retenção remota ainda precisam ser acompanhadas: gerações antigas não são apagadas automaticamente.

## Comandos

- `se-liga-brasil configure-voting-schedule --env-file CAMINHO_ENV`: aplica a fila privada e registra os dois jobs pg_cron de coleta e expurgo.
- `se-liga-brasil run-voting-pipeline --source senado --start-date YYYY-MM-DD --end-date YYYY-MM-DD --env-file CAMINHO_ENV`: coleta delimitada e publicação. Câmara usa `--source camara`.
- `--local-only`: executa validação/consolidação local, sem upload. Não conclui tarefas duráveis de publicação.
- `--cached-only`: no Senado, usa apenas originais já arquivados e perfis locais, sem chamadas à fonte. Requer `--max-identity-profiles 0`; pode publicar no Storage. Não consulta detalhes novos de matérias. Sem o arquivo exato do intervalo, falha explicitamente.
- `se-liga-brasil voting-worker --env-file CAMINHO_ENV --daemon --limit 100 --max-identity-profiles 10`: consome a fila continuamente, com cache, limites e cooldown.

A unidade `deploy/se-liga-brasil-voting-worker.service` mantém o trabalhador no systemd do usuário, com reinício em falhas e arquivos privados. O serviço foi habilitado com linger para continuar após logout. A máquina precisa estar ligada e ter rede; o pg_cron continuará enfileirando no Supabase se o trabalhador estiver offline, e a fila será retomada ao voltar. Não há um executor Python hospedado dentro do PostgreSQL. Hospedar esse trabalhador num servidor sempre disponível é uma implantação separada.

## Validação e limites de cobertura

Validação real: Senado/14-10-2026 gerou dois votos vinculados com ementa oficial e uma partição diária; manifesto e Parquets público/privado lidos de volta com hashes conferidos. A repetição retornou `pipeline_triggered=false`. Câmara/14-10-2026 não retornou registros na descoberta; nenhuma partição foi inventada nem enviada. Isso não comprova inexistência de atividade legislativa em outros endpoints ou períodos.

O coletor nominal Câmara foi validado por contratos oficiais e testes; nenhuma ausência ou modalidade é inferida a partir de lista vazia. Votos de pessoas sem identificação segura ficam pendentes nos arquivos originais; não são associados por nome isolado. Coleta truncada por orçamento não deve encerrar uma tarefa como plenamente enumerada. O serviço não declara cobertura completa da carreira. O canal de comissões do Senado ainda depende de vínculo de matéria/data para projeção canônica e não faz parte deste trabalhador de plenário.

Verificação final: 321 testes locais e dois testes SQL isolados aprovados, Ruff e revisão estrutural sem achados. As duas tarefas reais de Câmara/Senado para 14/10/2026 foram consumidas pelo serviço com processed=true e pipeline_triggered=false no replay.
