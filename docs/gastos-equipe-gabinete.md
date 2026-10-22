# Gastos publicados com a equipe do gabinete

O perfil apresenta o card **Gastos com gabinete**, com o total da última competência
coletada e o botão **Ver histórico**. O histórico contém a soma por cargo nos meses
exibidos e o detalhamento por competência, com link para a folha oficial. Não é um
total de todas as despesas do parlamentar nem uma indicação de remuneração pessoal.

## Fonte e cálculo

O coletor do Senado descobre os CSVs mensais no
[índice oficial de remunerações](https://www.senado.leg.br/transparencia/rh/servidores/consulta_remuneracao.asp).
Reconhece lotações de gabinete e escritórios de apoio explicitamente identificados
com o nome do senador. Outros órgãos, lideranças e unidades administrativas não são
incluídos. Linhas de categoria/vínculo parlamentar são excluídas. Apenas vínculos
EFETIVO e COMISSIONADO são aceitos para a equipe; formatos novos exigem revisão.

Todos os valores são processados com Decimal, sem ponto flutuante:

- Base bruta: remuneração básica, vantagens pessoais, função comissionada,
  gratificação natalina, horas extras, outras eventuais, abono de permanência e
  reversão do teto constitucional, com os sinais publicados.
- Conciliação: base bruta + IR + previdência + faltas deve ser igual ao líquido.
  Os descontos negativos são preservados.
- Bruto devido à equipe: base bruta + ajuste publicado de faltas.
- Outras verbas: diárias + auxílios + vantagens indenizatórias.
- Total do card: bruto devido à equipe + outras verbas.

IR e previdência retidos não são subtraídos do custo público nem adicionados de
novo. Encargos patronais não informados, aluguel, passagens e outras despesas fora
da folha não entram nesse cálculo. Ajustes e estornos negativos são preservados.
Folhas normais e suplementares contribuem para a soma. Não se deduplicam linhas
anônimas por valor/cargo: duas pessoas podem ter valores iguais. A quantidade de
lançamentos não é apresentada como quantidade de funcionários.

Uma linha inválida da equipe impede a ingestão daquela competência; não se publica
uma soma silenciosamente incompleta. O CSV original, seu hash, URL e data de coleta
permanecem preservados.

## Identidade e revisões

O nome da lotação identifica o gabinete, não o beneficiário do pagamento. A atribuição
exige nome parlamentar na lista oficial e nome civil de um perfil do Senado já
verificado, com nascimento compatível com a pessoa canônica. Homônimos sem resolução
não recebem valores. A referência ao perfil verificado e o hash da lista oficial
ficam na evidência da agregação. Não são criadas pessoas nem confirmados mandatos
por existir pagamento no gabinete.

Cada pessoa/competência é um fato agregado completo em `person_fact`, no namespace
`senado_cabinet_payroll`. A ingestão compartilhada preserva fontes e versões. A chave
inclui a versão de cálculo para permitir reprocessar o mesmo original sem sobrescrever
uma derivação anterior ou criar conflito artificial de timestamp. A leitura pública
seleciona a observação mais recente por mês, desempata pela versão do cálculo e não
soma revisões entre si. Uma nova importação do mesmo arquivo e recorte é idempotente.

A resposta pública contém somente valores agregados por cargo, competência e origem;
não expõe nomes de funcionários ou identificadores privados da resolução de identidade.

## Execução e cobertura

```sh
.venv/bin/se-liga-brasil collect-cabinet-payroll --max-partitions 12 --env-file /caminho/privado/.env
.venv/bin/se-liga-brasil collect-cabinet-payroll --months 2026-09,2026-08 --max-partitions 2 --env-file /caminho/privado/.env
```

O padrão coleta a última competência publicada; `--max-partitions` aceita de 1 a 12.
`--months` seleciona somente competências publicadas no índice. O comando é finito,
respeita cache, orçamento de bytes, pacing e cooldown e não instala agendamento.
O relatório fica em `data/senado-cabinet-payroll/collection-result.json`. Casas sem
coletor ou gabinete sem identidade confirmada exibem **Não disponível**, sem valor zero.

A consulta do perfil lê somente fatos armazenados, em uma consulta adicional; não
acessa sites oficiais. O histórico exibe até 120 competências e informa truncamento.
Meses ausentes permanecem ausentes. Na validação inicial foram coletadas 12 competências,
de outubro/2025 a setembro/2026, com 56 vínculos pessoa/competência em cinco perfis;
não representa cobertura dos 81 senadores nem de todas as casas legislativas.

A agregação do arquivo é O(n), com memória proporcional aos pares gabinete/cargo.
A consulta pública usa o filtro de pessoa e agrupa revisões por competência; a
composição das somas no histórico é O(k), com k pares mês/cargo retornados. O botão
usa diálogo HTML nativo, sem ampliar a exceção de JavaScript do projeto.
