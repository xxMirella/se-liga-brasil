# Coletor da Câmara Municipal de São Paulo

## Escopo entregue

`src/crawlers/cmsp/` contém aquisição, parsing, normalização, identidade revisada, staging, pipeline e projeção separados. O núcleo pode baixar e analisar partições anuais localmente; a ingestão é opcional mediante composição com o repositório existente. Não foi registrado na CLI nem no orquestrador, não executou coleta massiva e não alterou o banco de produção.

A descoberta usa apenas métodos declarados no [web service oficial SPLEGIS](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx):

- [`ProjetosPorAno`](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx?op=ProjetosPorAno), GET com `Ano`: identificação pública do projeto, ementa e campos que a resposta efetivamente publicar.
- [`ProjetosAutores`](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx?op=ProjetosAutores), GET com `ano`, `tipo` e `numero`: autores e subscritores. `tipo` e `numero` vazios consultam a partição anual; o coletor usa esse contrato documentado, sem enumerar números supostos.
- [`FasesDeDeliberacao`](https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx?op=FasesDeDeliberacao), GET com `ano`: descrição das deliberações coletivas quando publicada.

Esses métodos não declaram paginação. A unidade de planejamento é instituição + método + ano, compartilhada entre pessoas. Repetições de anos/domínios são deduplicadas antes da rede. Um limite excedido interrompe explicitamente, sem declarar os anos restantes consultados.

A validação de contrato incluiu WSDL oficial e uma resposta restrita a um projeto de `ProjetosAutores`, em 17/10/2026, confirmando `ArrayOfProjeto`, `Tipo`, `Numero`, `Ano`, `Autores/Autor/Nome`. Não houve varredura de anos ou de pessoas. As demais estruturas foram verificadas na documentação/WSDL e em fixtures anônimas; isso não equivale a testar todo o acervo remoto.

## Reutilização e limites

`MunicipalAcquisition` recebe `OfficialHttpClient`; reaproveita validação de host HTTPS, redirects oficiais, tentativas limitadas, pacing e bloqueios por host. `download_resource` reaproveita orçamento de bytes, cache, hash e arquivos originais por conteúdo. O coletor nunca reescreve o XML original durante normalização. Staging é derivado, separado e pode ser regenerado.

Padrões: até 6 recursos por execução, 10.000 registros por recurso, 40 MiB por download, 100 MiB por execução, lotes de 500, cache de 24 horas e intervalo mínimo de um segundo entre requisições. São configuráveis. Respostas 403/429 seguem a política compartilhada; não se criam tentativas paralelas por candidato.

O XML é lido em streaming; declarações de entidade/DOCTYPE e encodings com bytes nulos são recusados. Raiz e namespace inesperados, XML truncado, mudança do original e excesso de registros impedem a disponibilização do staging inteiro. Registros escalares inválidos ficam em rejeições com código e linha, produzindo cobertura parcial. Duplicatas idênticas são ignoradas; duplicatas conflitantes interrompem a partição. Nenhuma ingesta começa antes de validar o fechamento do XML.

A chave do projeto é a referência pública composta `tipo:número:ano`, no escopo da instituição. As chaves externas de **pessoas** não entram na normalização nem viram identidade interna. A varredura é O(bytes + registros + autores), com lookup/dedupe O(1) médio por chave. O índice de deduplicação exige O(registros) de memória dentro do limite; não se materializa o XML anual inteiro. O parsing faz uma passagem de segurança e uma de normalização, mantendo a ordem de grandeza linear.

## Identidade e significado dos fatos

O contrato de autores contém nome e chave da fonte, sem CPF/data de nascimento. Por isso nome sozinho não cria vínculo com `person.id`. Sem evidência revisada, o projeto pode ser ingerido, mas não ganha linha em `proposition_person`.

`ReviewedAuthorBinding` recebe UUID interno, nome oficial publicado, SHA-256 do artefato e referência de revisão de identidade pessoal. O chamador deve obter essa aprovação do serviço/processo de identidade existente; criar o objeto não realiza a revisão. A assinatura impede `name_only`, UUID inválido, referência vazia e nomes duplicados ambíguos. A evidência só se aplica ao artefato correspondente. Para revisões do mesmo nome em diferentes artefatos, executar cada partição revisada separadamente; a coleção geral permanece sem vínculo automático.

`Autores` gera papel `author` quando validado. `Subscritores` não é convertido automaticamente em autor/coautor. O WSDL de `Deliberacao` fornece apenas `Resultado`, sem data, identificador de sessão nem voto nominal: o texto permanece uma **observação de resultado coletivo sem data**. Não prova aprovação final, aprovação de lei ou voto individual. `currentStatus` continua `unknown`.

As referências de norma são preservadas como campos publicados em `normReference`, sem criar lei ou data de publicação artificial. Datas de proposição aceitam explicitamente `dd/mm/aaaa` ou `aaaa-mm-dd`; formato diferente gera rejeição revisável, sem interpretação heurística de datas incompletas. `fetched_at` marca observação, não ocorrência legislativa.

## Composição Python

Assinatura pública:

```python
collect_municipal_legislation(
    acquisition,
    years,
    *,
    domains=("projects", "authorship", "deliberations"),
    reviewed_bindings=(),
    repository=None,
)
```

É um gerador: consuma as partições para executar o trabalho. Exemplo de análise local limitada, dentro do ambiente Python do projeto:

```python
from pathlib import Path
import httpx

from crawlers.cmsp.acquisition import MunicipalAcquisition
from crawlers.cmsp.configuration import CrawlerConfiguration, OFFICIAL_HOSTS
from crawlers.cmsp.pipeline import collect_municipal_legislation
from service.acquisition.http_client import OfficialHttpClient

configuration = CrawlerConfiguration(Path("data/cmsp"), max_resources=1)
with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
    acquisition = MunicipalAcquisition(
        configuration, OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
    )
    for partition in collect_municipal_legislation(
        acquisition, [2021], domains=("projects",)
    ):
        print(partition["year"], partition["records"], partition["coverage"])
```

Não há comando CLI CMSP neste incremento. Para ingestão, compor `IngestionRepository(connection, SOURCE, MunicipalProjectionWriter(SqlBatchWriter(connection)), parser_version=PARSER_VERSION)` e passar `repository=` ao pipeline. O chamador deve executar `begin_run`/`finish_run`, controlar falhas, adquirir bloqueio e registrar a política de fonte como nos coletores existentes. O exemplo local acima não abre conexão com o banco.

## Tabelas e integração restante

O repositório genérico registra `source_record`, versões, artefatos e rejeições. A projeção `db/ingestion/cmsp_propositions.sql` insere a instituição `cmsp`, faz upsert de `proposition` e cria `proposition_person` apenas para autores com revisão explícita. Recurso de autoria/deliberação não apaga ementa nem reclassifica status de projeto existente. Os contratos normalizados passam pelo mecanismo de hash/idempotência do repositório. O scope do artefato inclui hash estável das evidências revisadas; registros vinculados usam versão técnica de evidência no externalKey do staging, mantendo a mesma officialKey do projeto. Assim uma revisão nova não é ignorada pelo cache de ingestão nem confundida com alteração da fonte no mesmo timestamp.

Este incremento não preenche `office_term`, `office_exercise`, `proposition_event`, `voting`, `person_vote`, `law` ou `proposition_law`. Descrições sem data ficam no registro de fonte, sem votação fictícia. Projeções SQL, persistência de rejeições e replay após revisão de identidade foram validados em esquema PostgreSQL isolado com rollback; não foram executados em produção.

Ainda faltam composição na aplicação/CLI e delegação do orquestrador por instituição/intervalo, registro de cobertura persistente e revisão de identidade pessoal. `partition_parsed` significa XML da partição encerrado com registros válidos; não significa trajetória completa nem garantia de que o serviço publicou todos os documentos históricos.

O [catálogo oficial](https://www.saopaulo.sp.leg.br/transparencia/dados-abertos/dados-disponibilizados-em-formato-aberto/) distingue acervo legado de 1948–1991, dados antigos de vereança e XML de votações plenárias. Esses recursos complementares, mandato/exercício e votos nominais não foram implementados neste núcleo. A abrangência do SPLEGIS e a ausência de dados de uma resposta não provam ausência de atividade pública.

## Verificação

`tests/test_cmsp_crawler.py`: 17 testes unitários de contratos, nomes/identidade revisada, resultados coletivos, limites, cache, integridade, duplicatas, erros XML, rejeições e despacho de projeção. Um teste adicional de integração validou proposição única, vínculo de autoria após revisão, replay idempotente e rejeição com o contrato do repositório, exclusivamente em esquema isolado e rollback. Fixtures sem pessoas reais; nenhum teste grava nas tabelas de produção. Ruff e revisão cognitiva do projeto sem achados.
