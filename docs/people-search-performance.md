# Carregamento da consulta de pessoas

A primeira navegação HTML sem `limit` retorna uma página de preparação sem consultar o banco. Um script local mínimo mede a área disponível abaixo dos filtros, a altura de um cartão e reserva espaço para navegação. Em seguida substitui a URL com `limit` entre 1 e 24. Nomes compridos usam uma linha com reticências e mantêm o texto completo no link e no título. Em telas onde os controles já ocupam toda a altura, o mínimo é uma pessoa, exigindo rolagem.

A medição ocorre ao abrir a consulta, não continuamente ao redimensionar a janela. O script não cria requisições de resize. Um link visível oferece 6 pessoas por página se o script falhar, estiver bloqueado ou desativado. O seletor permite escolher 6, 12 ou 24; não há itens adicionais carregados e escondidos para simular paginação.

A API mantém padrão de 6 pessoas e limite máximo validado de 100 para clientes explícitos. O SQL usa cursor por nome e UUID, sem OFFSET, e retorna no máximo tamanho da página mais um para indicar continuação: o padrão passou de 31 para 7 linhas, e a página HTML adaptada usa o tamanho medido mais um. A projeção contém apenas UUID interno, nome público e slug. Não são feitas consultas individuais por pessoa da lista.

Cada processo mantém cache exclusivamente da projeção JSON pública, com 30 segundos de validade, até 128 entradas e 2 MiB de conteúdo serializado. A chave inclui consulta, UF, cargo, partido, cursor, tamanho e data de referência. Resultados são reconstruídos para impedir mutações compartilhadas. Dezesseis locks limitados colapsam buscas simultâneas iguais; colisões podem serializar misses diferentes. Falhas não são armazenadas. `application.people_cache.clear()` invalida as entradas; correções externas tornam-se visíveis após no máximo a validade restante em cada processo.

O cache não armazena conexões, credenciais ou registros privados. A resposta HTTP dinâmica continua `no-store`; o cache curto é interno e não depende de CDN. A busca repetida idêntica foi validada com contadores: duas chamadas consecutivas fazem uma conexão e uma consulta, em vez de duas. A primeira busca ainda depende dos índices e filtros do PostgreSQL; não é O(1). O cache usa lookup médio O(1), serialização O(tamanho da página), e expiração O(capacidade), limitada a 128 entradas.

A exceção JavaScript foi autorizada pela usuária e está restrita à medição inicial, sem bibliotecas, código inline ou eval. O CSP autoriza apenas scripts locais. Não foram executados testes de carga no banco de produção, nem garantida capacidade para milhões de acessos.
