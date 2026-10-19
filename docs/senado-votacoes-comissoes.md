# Votações de comissões do Senado: contrato e limites

Verificação em 17/10/2026. Há contrato oficial utilizável para aquisição e normalização de votos nominais em comissões. Esta entrega acrescenta um coletor limitado e normalizadores em `src/crawlers/senado/committee_voting.py`, com testes fictícios isolados. **Não integra ainda a projeção PostgreSQL, o comando de plenário, o orquestrador nem a interface.** Nenhum dado de produção foi alterado nesta etapa.

## Contrato oficial confirmado

O [OpenAPI do Senado](https://legis.senado.leg.br/dadosabertos/v3/api-docs) publica `votacaoComissao/comissao/{siglaComissao}` e `votacaoComissao/materia/{sigla}/{numero}/{ano}`, versão 1. Ambos aceitam `dataInicio` e `dataFim` no formato `AAAAMMDD`. O serviço de plenário usa outro contrato e outra formatação de datas; seus identificadores não devem ser intercambiados.

O [XSD oficial VotacoesComissaov1](https://legis.senado.leg.br/dadosabertos/dados/VotacoesComissaov1.xsd) descreve o envelope `VotacoesComissao`, os metadados e a sequência `Votacoes/Votacao`. No JSON observado, uma sequência pode aparecer como lista ou objeto único. O OpenAPI declara a resposta dessas operações como string, sem esquema JSON detalhado; por isso a implementação também valida o formato efetivamente observado. Versão diferente de 1 é rejeitada para revisão.

Uma votação informa `CodigoVotacao`, casa/colegiado, reunião, identificação textual da matéria, descrição do objeto, totais e, quando publicada, a sequência `Votos/Voto`. Os votos têm nome parlamentar, casa parlamentar, partido observado, `QualidadeVoto` e `VotoPresidente`. Os códigos pessoais originais permanecem apenas no arquivo original e no contexto transitório de identificação.

## Amostras pequenas inspecionadas

- [CCJ, dezembro de 2025](https://legis.senado.leg.br/dadosabertos/votacaoComissao/comissao/CCJ.json?dataInicio=20251201&dataFim=20251231&v=1): cinco eventos, 114 observações nominais, 22.839 bytes. SHA-256 `b4874896b75416a4c8085dfa6f8a9ee13e424f025de3708f4130cce1ea8ab838`.
- [CAE, outubro de 2024](https://legis.senado.leg.br/dadosabertos/votacaoComissao/comissao/CAE.json?dataInicio=20241001&dataFim=20241031&v=1): dois eventos, 30 observações nominais, 6.558 bytes. SHA-256 `a3d91474e45f0bfdd504dac1e30c4786e2245f4fb76627980efcacd0879c2e03`.
- [PEC 148/2015, CCJ, 10/12/2025](https://legis.senado.leg.br/dadosabertos/votacaoComissao/materia/PEC/148/2015.json?comissao=CCJ&dataInicio=20251210&dataFim=20251210&v=1): somente metadados, 220 bytes. SHA-256 `53898f03cc29cddadd4f4608209fc07425bd90397dccdeefcc5ce3a130f77b82`. Essa resposta não comprova inexistência de deliberação nem permite atribuir votos pessoais.

Os números são observações dessas respostas, não contagens de pessoas únicas nem cobertura integral dos períodos. A normalização dos sete eventos e 144 observações foi executada localmente; não houve publicação desses registros no banco.

## Semântica preservada

A chave técnica é `committee:{casa}:{codigo_colegiado}:{codigo_votacao}`. Assim, uma numeração igual à do plenário ou de outro órgão não funde eventos. Reunião, colegiado e objeto permanecem separados. Na amostra da CCJ há quatro eventos da mesma matéria na mesma reunião, incluindo requerimentos e relatório; seus votos não são automaticamente votos no texto principal.

`DataHoraInicioReuniao` é o início da reunião, **não o horário da votação**. O normalizador preserva `meeting_started_at_local` e `meeting_date`, sem atribuir fuso inexistente na resposta. `occurred_on` continua nulo e `date_precision` desconhecida. Uma futura interface pode mostrar o mês da reunião como referência explicitamente rotulada, mas não deve apresentá-lo como data exata comprovada da votação.

Foram observados `QualidadeVoto=S` e `N`, convertidos em favorável e contrário. Outros códigos permanecem desconhecidos com seu valor original; não são presumidos como ausência, abstenção ou obstrução. `VotoPresidente` é preservado separadamente: ser presidente não elimina uma escolha publicada, e a indicação de quem presidiu a reunião não cria um voto inexistente. O XSD define esse campo como booleano, mas não enumera os valores possíveis de `QualidadeVoto`.

O serviço não fornece resultado coletivo estruturado nessas amostras. O normalizador não deduz aprovação ou rejeição pelos totais, nem transforma palavras de uma descrição em lei aprovada. Partido na votação é observação contextual e não substitui filiação atual.

A identificação pessoal reutiliza o índice de perfis oficiais já verificados por nome completo e nascimento. O resolvedor específico aceita apenas pessoas publicadas como integrantes da casa `SF` nesse índice; comissões mistas podem incluir outra casa, cujos votos permanecem sem vínculo até haver identidade validada no domínio correto. Nome parlamentar sozinho não identifica pessoa.

## API disponível e desempenho

`collect_committee_votings(acquisition, committee_code, start, end, maximum=1000)` retorna registros normalizados, artefato imutável e estado de publicação/cobertura. Permite até 31 dias inclusivos e 1.000 eventos por chamada; sigla, datas e orçamento são validados antes de HTTP. Reutiliza `SenateAcquisition`, cache, arquivos por hash, limites de bytes, transporte oficial, espaçamento de requisições e tratamento de indisponibilidade existentes. Não dispara chamadas por parlamentar.

`resolve_committee_individuals(rows, profile_index)` produz votos associados a UUIDs internos e quantidade de observações ainda sem identidade. Não acessa rede ou banco durante o loop. Respostas sem registros recebem `not_published_in_response` e cobertura `not_verified`. Erro HTTP, versão inesperada, duplicação de evento ou divergência de comissão/período interrompem a coleta, sem fabricar sucesso.

Para e eventos e n observações individuais, a normalização custa O(e+n); a resolução por índice tem busca média O(1) por observação, com custo total O(n). A saída exige O(e+n) de memória, limitada por orçamento de eventos e de download. Essa fatia não declara ingestão inteira O(1).

## Integração canônica que ainda falta

1. Vincular a identificação textual da matéria a uma proposição oficial única, com evidência. O contrato não fornece `idProcesso`; não criar processo fictício nem outra proposição apenas para acomodar o evento.
2. Definir representação explícita da data de referência da reunião, preservando a ausência de data exata do voto. O pipeline de plenário exige outro contrato temporal e não deve receber estes registros diretamente.
3. Acrescentar suporte de projeção ao papel de presidência separado da escolha e às casas presentes nas comissões mistas, preservando revisões e proveniência.
4. Validar tramitação, parecer ou ata para obter resultado coletivo e efeito sobre o objeto correto. Identificação da matéria, aprovação de requerimento e aprovação final são fatos diferentes.
5. Publicar uma partição pequena em schema de teste, testar replay e retificação, e só então acrescentar comando e rota de orquestração. Resposta sem nominal e ausência de cobertura histórica devem continuar visíveis.
