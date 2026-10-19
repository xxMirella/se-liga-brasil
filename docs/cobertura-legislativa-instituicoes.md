# Coletores legislativos por instituição

Contrato verificado em 17/10/2026. Esta entrega acrescenta aquisição e normalização; não executa ingestão em produção nem declara trajetória completa. O roteamento exige instituição efetivamente conhecida. UF nunca encaminha, sozinha, atividade municipal à assembleia estadual.

## ALESP

`crawlers.alesp.legislative.collect_proceedings` recebe configuração de aquisição existente, cliente oficial, conjunto de documentos e intervalo inclusivo. Reutiliza `download_resource`, cache imutável, orçamento e `local_records.xml_rows`. Um arquivo compartilhado atende todos os documentos solicitados; seleção local ocorre em streaming.

O [layout oficial de documento_andamentos](https://www.al.sp.gov.br/repositorioDados/docs/processo_legislativo/documento_andamentos.pdf) publica chave do documento, data, ordem, etapa, comissão, tipo e descrição. O recurso ZIP é o endereço HTTPS correspondente ao endereço do catálogo. O tamanho documentado é aproximadamente 32 MB compactado e 905 MB descompactado. A configuração de folha existente limita recurso a 10 MB: o chamador precisa fornecer configuração de aquisição apropriada, mantendo limites explícitos; o coletor não aumenta limites silenciosamente.

O normalizado entrega chave estável do andamento, chave técnica da proposição, data, órgão, etapa e descrição. A chave não identifica pessoa. `final_outcome` permanece nulo: texto contendo aprovação não prova aprovação final. A leitura só aceita datas no formato dia/mês/ano pelo normalizador compartilhado; divergências são erro de contrato, nunca cobertura vazia.

Domínio operacional novo: tramitação. Resultados finais, vínculo estruturado com lei e votos nominais permanecem **unsupported**. A cobertura temporal do catálogo é N/A; intervalos solicitados não se tornam garantias históricas. O ZIP completo não foi baixado nesta tarefa. Validação de comportamento utiliza arquivos mínimos isolados; o layout foi conferido na fonte oficial.

## Senado

O [OpenAPI oficial atual](https://legis.senado.leg.br/dadosabertos/v3/api-docs) marca endpoints legados de matéria como deprecated. O coletor usa `processo/{id}.json?v=1` e `votacao.json?dataInicio=AAAA-MM-DD&dataFim=AAAA-MM-DD&v=2`, reutilizando `SenateAcquisition`, downloader, cache e cliente existentes.

`collect_process_details` deduplica no máximo 100 processos antes das requisições. Produz identificação da proposição, tipo, data de apresentação, ementa, descrição do status e informes de tramitação com órgão/data. Autoria, deliberação e norma gerada são evidências estruturadas preservadas, ainda sem projeção automática para autoria identificada, resultado final ou lei. A vinculação de pessoas continua exigindo identificação do serviço existente; códigos de parlamentar não devem virar identificadores canônicos de pessoa.

`collect_votings` consulta uma partição compartilhada de no máximo 31 dias. O contrato OpenAPI descreve lista sem parâmetro de paginação. O normalizado separa resultado coletivo, objeto votado, órgão, totais e evidência nominal. Votação secreta sempre produz lista nominal vazia, mesmo se o payload fornecer votos. Código coletivo de aprovação nunca se transforma automaticamente em aprovação final da proposição.

Uma resposta real de processo foi conferida, incluindo informes históricos. Duas pequenas consultas de votação retornaram listas vazias; o contrato nominal foi validado no OpenAPI, e seu comportamento por testes isolados. Portanto, não houve comprovação de carga nominal real nem de abrangência histórica completa. Lista vazia não autoriza concluir ausência de votos de uma pessoa.

Domínios novos de aquisição: detalhes de proposições, tramitação e votações. Leis e resultados finais classificados permanecem **unsupported** enquanto não houver normalização e validação semântica próprias. O coletor de detalhes exige processos previamente descobertos: não substitui descoberta histórica por autoria. IDs técnicos de processos e votos identificam eventos; o UUID interno continua identificando pessoas.

## ALERJ

`crawlers.alerj.legislative.legislative_capability` informa `unsupported` e `LEGISLATIVE_CONTRACT_NOT_VALIDATED` para qualquer domínio legislativo novo. Não faz requisições. Perfil e folha já existentes continuam tendo seu próprio contrato; isso não comprova cobertura de atividade legislativa. Nenhum endpoint de tramitação, lei ou voto foi inventado nesta entrega.

## Integração e cobertura

Cada módulo expõe capacidade por instituição, domínio e intervalo solicitado. Limites históricos reais permanecem nulos quando desconhecidos. `supported` significa que existe adaptador do domínio; não significa intervalo integralmente consultado ou fatos ingeridos. A orquestração deve consultar capacidade antes de requisitar e manter `unsupported` sem tentativas de rede.

Próxima integração necessária: chamar coletores pelo planejamento da carreira; converter seus normalizados nos contratos de ingestão de `proposition`, `proposition_event` e `voting`; resolver identidade nominal antes de `person_vote`; validar deliberação/norma antes de `law` e `proposition_law`. Anexar URL, hash e data do artefato a cada lote, preservando arquivos originais. Somente registrar cobertura após consumo integral dos iteradores e sucesso transacional. Falha de rede, esquema ou XML mantém a partição pendente; nenhuma função retorna marcador artificial de completude.

Complexidade: ALESP O(n) nos andamentos do export e O(k) memória para documentos selecionados, além de um registro XML. Senado detalhes O(k log k + e) pela ordenação das chaves e pelos eventos; no máximo k requisições únicas, cacheadas. Votações O(v) por partição e memória O(v) limitada pelo teto de download. Hash/set oferece consulta média O(1) por chave, sem prometer leitura completa O(1).

Verificação: dez testes de limites, deduplicação antes da rede, schema inesperado, falha de transporte, voto secreto, não inferência de aprovação e streaming por documento/período; Ruff e revisão estrutural sem achados.
