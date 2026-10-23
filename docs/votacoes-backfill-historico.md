# Backfill histórico de votos

O horizonte de consulta pode começar em 2000. Isso não significa presumir que a pessoa
exercia cargo em 2000. O planejamento cruza o período solicitado com exercícios institucionais
canônicos e sustentados por fonte oficial. Candidatura, nome parecido e biografia não substituem
essa evidência.

Para Flávio Bolsonaro, o exercício do Senado verificado começa em 01/02/2019. Em 22/10/2026,
o intervalo gera 93 partições mensais. O período anterior na ALERJ exige outro conector:
o coletor atual de remuneração/partido não enumera votos nem autoria na plataforma Lotus Notes.
Essa pendência é de implementação, não uma declaração de inexistência de atividade legislativa.

## Planejamento e execução

```sh
se-liga-brasil enqueue-voting-history --source senado \
  --person-id 4c30de36-97ec-4f4c-af89-dd16ff3d99a9 \
  --start-date 2000-01-01 --end-date 2026-10-22 --max-jobs 10 --env-file /caminho/.env
se-liga-brasil voting-worker --source senado --max-jobs 10 --limit 100 \
  --max-processes 0 --max-identity-profiles 0 --env-file /caminho/.env
```

O primeiro comando só planeja; o segundo coleta, valida identidade e publica no Storage privado
pelo pipeline diário existente. O parâmetro `--max-jobs` limita o lote. Pedidos repetidos reutilizam
jobs com o mesmo intervalo e fonte, inclusive concluídos ou aguardando retry; não zeram tentativas.
O worker exclui fontes em cooldown antes de adquirir lease e gastar uma tentativa.

Não executar um segundo worker em paralelo ao serviço systemd do projeto. Para backfill manual,
pausar temporariamente esse serviço e reiniciá-lo ao final, preservando a fila e o cron.

Cada mês usa a API `votacao.json?dataInicio=AAAA-MM-DD&dataFim=AAAA-MM-DD&v=2`, com orçamento
explícito de 100 votações no exemplo. Se excedido, o job falha e não certifica enumeração.
`--max-processes 0` evita requisições extras: usa a ementa oficial publicada no próprio original,
sem gerar descrição. `--max-identity-profiles 0` reutiliza apenas perfis oficiais já verificados por
nome completo e nascimento; pessoas ainda sem prova independente ficam sem associação.

Respostas `votos=null` mantêm disponibilidade nominal desconhecida/não publicada e não geram
votos individuais. Votações secretas também não expõem escolhas pessoais. Fevereiro de 2019,
por exemplo, retornou quatro votações secretas; zero escolhas publicáveis não significa falta
de atividade. Outubro de 2019 confirmou a cobertura histórica da API com a PEC 6/2019, incluindo
votações 6024 e 6046 de Flávio. Todas as respostas usadas pelo pipeline ficam arquivadas com hash.

Um job processado comprova execução e publicação daquele intervalo, não carreira completa:
comissões, autoria, leis, fontes não implementadas e identidades não resolvidas permanecem
explicitamente fora da cobertura certificada. Salários do Senado continuam em espera.

## Fontes históricas da ALERJ identificadas

A [Sinopse da Atividade Legislativa de Flávio Bolsonaro em 2018](https://www2.alerj.rj.gov.br/leideacesso/spic/arquivo/Flavio_Bolsonaro_2018.pdf)
é um original institucional de 41 páginas. A página 6 registra declaração de voto contrário ao
PL 1029/2011 em 07/02/2018; a página 11 registra explicação de voto contrário ao PLC 05-A/2015
em 04/04/2018. O documento também mistura discursos, pedidos de verificação, autoria e
encaminhamentos: cada categoria exige seu próprio normalizador e prova. Esses registros
não foram ingeridos por nome isolado nem convertidos automaticamente em votos nominais.

O [Jornal da ALERJ de 16 a 22/06/2003](https://www2.alerj.rj.gov.br/jornalalerj/jornalalerj12.pdf)
publica perfil do parlamentar no primeiro mandato. O [perfil institucional do Senado](https://www25.senado.leg.br/web/senadores/senador/-/perfil/5894)
e a documentação de exercício são as fontes para o início no Senado em 2019. A existência
desses arquivos permite desenvolver o conector histórico da ALERJ sem declarar falta de
atividade antes de 2019 ou supor mandato em 2000.
