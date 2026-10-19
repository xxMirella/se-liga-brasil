# Declarações eleitorais de bens no perfil público

O módulo `service.public_profile.assets.get_public_assets(repository, person_id, as_of)` consulta `database.public_assets.PublicAssetsRepository` em uma transação somente leitura. O identificador recebido é exclusivamente o UUID interno da pessoa. A tabela `candidate_asset_declaration` já é preenchida pela projeção de bens do TSE; este serviço não altera arquivos originais nem ingere registros.

## Contrato de integração

Acrescentar o resultado no campo `assets` do perfil ou disponibilizar uma rota específica. Instanciar `PublicAssetsRepository(connection)` e chamar `get_public_assets(repository, person_id, as_of)` com a mesma data de referência do perfil. O módulo não altera o transporte nem a renderização existentes.

O resultado contém `person_id`, `as_of`, `declarations`, `coverage` e `current_net_worth`. Cada declaração reúne `election_year`, `kind=electoral_asset_declaration`, `currency=BRL`, `recorded_total`, `total_scope=available_records_only`, `item_count`, `items`, `items_truncated`, `value_quality_status`, `source_generated_at`, `source` e `coverage=completeness_unverified`.

Cada item expõe somente `asset_type`, `declared_value`, `value_quality_status` e `official_url`. Valores monetários são strings decimais, preservando precisão e sinais. Descrições livres são omitidas porque podem conter contas, endereços e documentos pessoais. Não são expostos sequenciais de candidatura, arquivos internos, payloads ou documentos pessoais. Links públicos são HTTPS no domínio do TSE ou seus subdomínios.

## Significado e limites

Mostrar “Bens declarados à Justiça Eleitoral — ano” e “Soma dos registros disponíveis”. A soma não atesta integralidade da declaração, valor de mercado, patrimônio líquido ou patrimônio atual. Valores negativos da fonte permanecem negativos e geram `requires_review`; não são corrigidos por valor absoluto.

Ausência de registros resulta em cobertura `unknown`, nunca patrimônio zero. Mesmo havendo registros a cobertura permanece `partial`, porque a projeção atual não contém recibo que prove todos os itens/anos ou declaração explícita de inexistência de bens. Datas de geração da fonte não representam datas de aquisição dos bens. O parâmetro `as_of` limita anos eleitorais; a projeção atual não permite reconstrução bitemporal das versões anteriores da declaração.

A apresentação limita 100 anos e 100 itens por ano, sinalizando truncamento. O total considera todos os registros disponíveis do ano, mesmo quando itens da apresentação são limitados. Registros de mais de uma candidatura no mesmo ano são agrupados no ano: a soma é estritamente dos registros armazenados, não uma declaração individual certificada nem uma medida comparável de evolução patrimonial.

## Custo e validação

São no máximo três consultas por perfil (existência, agregados por ano e itens em lote), sem N+1 e sem rede oficial. Há índice existente em `(person_id, election_year)`. Agregação é O(n), para n itens da pessoa; ordenação dos itens pode exigir O(n log n). A resposta limita memória a 100 × 100 itens mais resumos. A camada de banco faz o processamento necessário sobre todos os itens selecionados para não perder a precisão do total. A revisão estrutural não substitui a verificação da cobertura das fontes.

Testes unitários usam dados fictícios e verificam ausência de informações privadas, sinais negativos, falta de cobertura, truncamento, inexistência da pessoa e segurança dos links. Nenhum teste escreve na base de produção.

## Fotos oficiais: correção complementar

A Câmara já fornece `ultimoStatus.urlFoto`, normalizada em `photoUrl` e projetada quando `person.photo_url` está vazio. O Senado fornece `IdentificacaoParlamentar.UrlFotoParlamentar` nos perfis completos e no cadastro de parlamentares em exercício. O normalizador do Senado agora mantém esse campo; a projeção preenche somente fotos ausentes. A versão do parser foi incrementada para permitir reprocessamento dos downloads sem alterar os arquivos.

`normalization.official_media.normalize_official_media_url` valida HTTPS e uma lista explícita de hosts. A conversão HTTP para HTTPS é opcional e usada somente nos hosts oficiais do Senado, cujas respostas locais antigas apontam HTTP. Credenciais em URL, portas inesperadas, fragmentos e hosts semelhantes são rejeitados.

Um preenchimento pontual das duas pessoas selecionadas na validação da interface encontrou uma foto já cadastrada e acrescentou uma foto do Senado: ambas passaram a ter `photo_url`. A imagem acrescentada respondeu HTTPS 200 com tipo `image/*`. A identidade foi conferida por nome completo e nascimento únicos, excluindo aliases, e por fato previamente verificado vinculado à fonte. O manifesto e o arquivo original tiveram seu hash conferido; a referência ao `source_record` foi preservada em `person_fact` com `field_name=official_photo`. Nenhum download original foi alterado e nenhum identificador externo pessoal foi acrescentado.

Esse preenchimento pontual não certifica cobertura fotográfica de todos os registros. ALESP/TSE ainda precisam de coletores próprios de fotos ou de extensão das fontes já validadas, respeitando identidade e proveniência.

## Apresentação HTML

`service.public_profile_web.asset_declarations.render_asset_declarations(profile)` lê o campo público `assets`. Renderiza cartões por ano com soma dos registros disponíveis, quantidade, geração da fonte e detalhes expansíveis dos tipos/valores. Cada ano exibe no máximo 100 itens e o perfil no máximo 100 anos, com aviso de truncamento quando informado pelo serviço. Isso limita a apresentação; não há nova paginação remota nem busca de arquivo no navegador. URLs oficiais e textos são validados/escapados. A formatação monetária não recalcula nem substitui o total fornecido pelo serviço.
