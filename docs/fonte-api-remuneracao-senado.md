# Fonte oficial: API nominal de remunerações do Senado

Validada em 22/10/2026. Publicador: Senado Federal, por meio de seu serviço de
Dados Abertos Administrativos. A consulta é pública e não exige CAPTCHA nem chave
de API nos endpoints verificados. A origem é oficial do Poder Legislativo federal.

## Endpoints

- Documentação interativa: [Swagger do serviço administrativo](https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html?configUrl=%2Fadm-dadosabertos%2Fswagger-config.json).
- Contrato legível por máquina: [OpenAPI](https://adm.senado.gov.br/adm-dadosabertos/v3/api-docs).
- Folha nominal mensal: `GET https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/{ano}/{mes}`.
- Exemplo validado: [setembro de 2026](https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/2026/9).
- Cadastro parlamentar ativo: [servidores com vínculo PARLAMENTAR e situação ATIVO](https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/servidores?tipoVinculoEquals=PARLAMENTAR&situacaoEquals=ATIVO).

O endpoint de remunerações retorna uma lista JSON, com valores monetários em strings
no padrão brasileiro, por exemplo `"1.000,00"`. O mês na URL não precisa de zero à
esquerda. A resposta de setembro/2026 examinada continha 10.754 lançamentos nominais,
incluindo funcionários e parlamentares. Essa quantidade é uma fotografia da consulta,
não um total permanente de beneficiários únicos.

## Campos da folha

Identificação e período: `sequencial`, `nome`, `ano`, `mes`, `tipo_folha`.

Componentes salariais: `remuneracao_basica`, `vantagens_pessoais`,
`funcao_comissionada`, `gratificacao_natalina`, `horas_extras`, `outras_eventuais`,
`abono_permanencia`, `reversao_teto_constitucional`.

Descontos e líquido: `imposto_renda`, `previdencia`, `faltas`, `remuneracao_liquida`.

Verbas preservadas separadamente do salário: `diarias`, `auxilios`,
`vantagens_indenizatorias`.

A folha não informa nascimento, CPF, cargo, lotação ou vínculo. O cadastro parlamentar
complementar informa nome, vínculo, situação, lotação e identificadores do próprio
cadastro. A API legislativa de perfis fornece o nascimento para confirmar a pessoa
canônica. Lotação de um gabinete não identifica o destinatário de um pagamento.

## Identificadores não intercambiáveis

O campo chamado `sequencial` no cadastro não corresponde ao campo de mesmo nome na
folha. `fcodigo` do portal legado também não pode ser usado como chave da folha.
Essa diferença foi observada para parlamentares conhecidos em ambas as respostas.
Não há contrato validado que permita relacionar esses campos por igualdade.

O crawler mantém os valores em campos separados: `administrativeRegistrySequence`
e `payrollRecipientSequence`. O identificador da folha é interpretado no contexto
do original mensal consultado, sem assumir estabilidade global entre relatórios.
A chave da projeção mensal usa a pessoa canônica e a competência; alteração de um
sequencial de origem não deve criar outro pagamento para o mesmo mês.

## Associação com pessoas da base

O coletor exige identidade previamente verificada por nome civil e nascimento no
perfil oficial do Senado, ou CPF validado quando disponível. Exige também nome civil
sem ambiguidade no cadastro parlamentar e um único beneficiário da folha para o
mesmo nome completo normalizado. Não usa aproximação textual, partido político ou
valor do subsídio para resolver identidade. Não cria novas pessoas a partir da folha.

Nomes homônimos, identidades contraditórias, ausência de folha normal e pessoa sem
pagamento publicado mantêm a pendência aberta. A ausência de um nome na resposta não
prova ausência de remuneração, exoneração ou fim de mandato. O cadastro ativo atual
não certifica a totalidade de vínculos históricos.

## Cálculo e histórico

Todos os valores são validados com Decimal. A soma dos oito componentes salariais,
mais IR, previdência e faltas com os sinais publicados, deve resultar no líquido.
O bruto devido inclui o ajuste de faltas. IR e previdência são preservados como
retenções; diárias, auxílios e indenizações não são apresentados como salário líquido.

Folhas `Normal` e `Suplementar` são preservadas em `payrollEntries` e somadas no agregado
mensal. Não se descarta uma linha apenas porque a pessoa já tem outro lançamento no
mês. Outros tipos de folha exigem validação do formato. Somente complemento, sem folha
normal, não comprova o salário mensal completo.

O arquivo JSON original é baixado pelo cliente oficial compartilhado, com allowlist
HTTPS, limites, pacing, cache e checksum. Normalização e confirmação pessoal antecedem
o staging. A ingestão genérica preserva `source_record`, versões, origem e competência;
a projeção pública usa `person_payroll_payment`, com `identity_status=verified`.
Reimportações idênticas não duplicam pagamentos e correções preservam o histórico.

O orquestrador usa `dispatch --fields current_salary --sources senado`; a competência
padrão é o último mês encerrado no fuso America/Belem. Um lote compartilha o download
do cadastro e da folha, em vez de repetir a requisição mensal para cada pessoa. O
arquivo pode conter pessoas que não existem na base; seus dados permanecem no original,
sem vínculo pessoal presumido. Não publicar os arquivos brutos no frontend.
Pedidos exclusivamente de salário reutilizam primeiro os perfis oficiais verificados
na base; os demais seguem a confirmação pela API legislativa. Uma falha posterior
nessa API preserva o resultado dos salários já processados no relatório do lote.

Para coletar pela API administrativa usando identidades oficiais já verificadas na
base, sem precisar atualizar os perfis na API legislativa, executar:

```bash
se-liga-brasil collect-senado-payroll --limit 100 --env-file /caminho/privado/.env
```

O limite aceito é de 1 a 100 pessoas; `--person-id UUID` restringe a uma pessoa.
Pessoas sem pagamento da competência são priorizadas. O comando mantém o bloqueio
de concorrência por fonte, usa o mesmo staging e a mesma projeção da coleta normal,
e reavalia as pendências de completude das pessoas processadas. Ele não consulta
o host legislativo nem altera seu cooldown. Não confirma identidades novas apenas
com os nomes presentes na folha.

Na execução de 22/10/2026, o crawler baixou e arquivou a folha de setembro/2026 e
o cadastro parlamentar. Foram ingeridos cinco agregados mensais para pessoas com
perfil previamente verificado, sem rejeições. A repetição retornou cinco registros
inalterados e nenhum novo. A ampliação para outras pessoas ainda depende da
validação de identidade: a API legislativa retornava HTTP 503 durante a execução.

## Diferença em relação às outras fontes

O CSV legado de remunerações tem cargo e lotação, mas não nome do beneficiário; continua
útil para a soma de gastos da equipe por gabinete e cargo. A consulta individual legada
apresentou CAPTCHA. A API nominal documentada aqui é a fonte direta para o salário
individual, sem depender de resolver esse CAPTCHA.
