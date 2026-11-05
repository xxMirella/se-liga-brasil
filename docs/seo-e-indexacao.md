# SEO e indexação do Se Liga, Brasil

Implementação de 02/11/2026 para a origem pública informada: `https://seligabrasil.gov`.
O servidor local continua em `http://127.0.0.1:8787`. Alterar o código e verificar
o servidor local não publica a aplicação, configura DNS ou registra a propriedade no Google.

## Descoberta dinâmica

- `/robots.txt` anuncia a origem pública de `/sitemap.xml`, permite páginas e recursos
  do portal e exclui a API da descoberta por rastreamento.
- `/sitemap.xml` é um índice XML gerado a partir das identidades públicas e das
  projeções anuais existentes. Não depende de exportação manual nem do diretório `data/`.
- `/sitemaps/pages.xml` contém as páginas gerais canônicas (incluindo `/panorama`) e as esferas do guia.
- `/sitemaps/people-<prefixo>.xml` enumera perfis canônicos por intervalo de UUID;
  aliases de identidade não entram. Nenhum documento pessoal, nome civil privado ou
  identificador de fonte é exportado. A leitura não monta o perfil de cada pessoa.
- Não há mais `/sitemaps/panorama-<território>.xml`: o `/panorama` deixou de ter URLs por
  território, ano ou visualização (ver `docs/panorama-maioria-nacional.md`). O índice lista
  apenas `pages.xml` e os fragmentos de perfis, e a leitura do banco que servia aos
  panoramas por território foi removida.

O índice agrupa prefixos de um dígito enquanto houver até 5.000 perfis no grupo;
grupos maiores se dividem em prefixos de dois dígitos. Cada XML verifica os limites
de 50.000 entradas e 50 MiB, sem truncamento silencioso. O catálogo em memória e o
cache compartilhado HTTP têm validade de 60 segundos cada. Novas identidades e
projeções são descobertas nas leituras seguintes; em caches sobrepostos pode haver
até aproximadamente dois minutos de atraso. Não há aquisição remota por URL.

## Atualizações e datas honestas

Páginas estáticas e perfis não recebem um `lastmod` inventado. O `person.updated_at`
não prova a data de mudança de todos os domínios exibidos no perfil, como autoria,
bens, folha e presença; por isso não é usado como se cobrisse o conteúdo inteiro.
Essas URLs são incluídas dinamicamente, e os perfis continuam servindo os dados
atuais do banco a cada leitura, sem reconstrução estática. A ausência de `lastmod`
é válida no protocolo e não impede que o Google recapture o perfil.

Não foram adicionados `priority`, `changefreq` ou o antigo ping de sitemap. O Google
ignora os dois primeiros e o ping antigo não é o fluxo de submissão recomendado.
Descoberta, rastreamento e indexação são etapas diferentes: não há promessa de
indexação imediata, posição nos resultados ou indexação de todas as URLs.

## HTML, URLs canônicas e compartilhamento

As respostas HTML incluem título, descrição, canonical absoluto, robots, Open Graph,
Twitter Card e JSON-LD de `WebSite`/`WebPage`. Perfis descrevem uma entidade `Person`
com nome público e URL, sem documentos pessoais. O JSON-LD é dado não executável;
os caracteres que poderiam encerrar uma tag de script são escapados.

- No `/panorama`, o canônico é `/panorama`; apenas `leg` válido (legislatura) é uma página
  distinta (`/panorama?leg=2019`). `house`, `mode`, `hl`, `scen`, `prop`, `view` e `bloc` são
  interação e canonizam para a mesma página, sem `noindex`. Título: "Panorama político: quem
  tem a maioria? · Se Liga, Brasil" (com a legislatura quando `leg` está presente).
- Parâmetros equivalentes, ordem de filtros, barras finais e aliases `/sobre`
  convergem para uma representação canônica. `/` é a página institucional canônica.
- A atividade completa do perfil tem canonical `?tab=activity`. Filtros e cursores
  operacionais não criam um espaço de busca indexável ilimitado.
- Resultados de busca com filtros, panoramas
  sem nenhuma legislatura com dados e erros usam `noindex`. As páginas continuam acessíveis para navegação.
- `/pessoas` entrega a primeira página real no HTML inicial. A medição de viewport
  continua usando somente o script já autorizado; não é necessária para descobrir
  os primeiros perfis ou a paginação. Falha do banco agora retorna 503, em vez de
  uma tela de carregamento com HTTP 200.
- APIs e erros têm `X-Robots-Tag: noindex, follow`; ambientes Vercel preview e
  development também recebem a diretiva. A CSP não foi enfraquecida.

O domínio canônico vem da configuração, nunca do cabeçalho `Host` do visitante.
Sitemaps e robots têm ETag e revalidação; alterações no conteúdo mudam o ETag.
GET e HEAD funcionam no transporte local e no WSGI da Vercel.

## Configuração e publicação

As entradas estão documentadas em `.env.example`, sem credenciais ou valores
preenchidos. Variáveis de ambiente relevantes:

- `PUBLIC_SITE_URL`: origem HTTPS, sem caminho, query ou credenciais; padrão
  `https://seligabrasil.gov` quando ausente ou vazia.
- `SEARCH_INDEXING_ENABLED`: `true` por padrão; `false` aplica noindex e deixa de
  anunciar o sitemap no robots. Não funciona como autenticação ou controle de acesso.
- `VERCEL_ENV`: fornecida pela plataforma; preview e development não são indexáveis.
- `GOOGLE_SITE_VERIFICATION`: token público opcional fornecido pelo Search Console
  para verificação por tag HTML. A verificação de propriedade de domínio usa DNS
  e não é substituída por essa tag.

Para tornar a entrega visível ao Google:

1. Publicar esta versão no domínio informado, com HTTPS e configuração de produção.
2. Abrir `https://seligabrasil.gov/robots.txt` e `https://seligabrasil.gov/sitemap.xml`
   e confirmar respostas 200, origem correta e ausência de noindex de preview.
3. Verificar a propriedade no Google Search Console, por DNS ou pelo método
   disponível na conta; o código não configura o domínio nem acessa essa conta.
4. Enviar uma vez `https://seligabrasil.gov/sitemap.xml` no relatório de sitemaps.
   Os filhos são descobertos pelo índice, sem reenviar cada perfil a cada atualização.
5. Usar a inspeção de URL em amostras de perfil e do panorama nacional (com e sem `leg`);
   acompanhar páginas descobertas, rastreadas, indexadas e possíveis erros.

## Validação e custo

O registro local da varredura real está em `data/seo/http-validation-20261102.json`:
47 sitemaps filhos, 19.090 URLs distintas, 16.005 perfis, 3.076 panoramas por
território e ano (modelo anterior, hoje removido) e nove páginas gerais. Foram conferidos XML, origem, ausência de duplicatas, canonical de
todas as URLs, amostras HTML e respostas HEAD. A contagem é uma fotografia de
02/11/2026, não uma constante da aplicação.

Os testes SQL usam esquema isolado e rollback obrigatório. Exercitam novas pessoas,
aliases, limites por prefixo, anos futuros, dados ausentes e municípios sem catálogo.
Os testes locais cobrem escaping, mudanças de ETag, equivalência de filtros, noindex,
metadados no HTML inicial, perfis sem JavaScript e prevenção de injeção em JSON-LD.

O índice varre P identidades para agrupar até 256 buckets. Um shard de perfis usa intervalo na chave primária: leitura esperada
O(log P + K), mais o anti-join indexado de aliases, com K limitado. XML e enriquecimento
HTML custam O(tamanho da saída), com memória proporcional à resposta. Não há N+1
remoto nem leitura do histórico de cada pessoa para montar o sitemap.

Referências oficiais: [sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap),
[canonical](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls),
[noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing),
[limites da indexação](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview).

Verificação final: suíte completa com 2.602 testes aprovados e 99 condicionados a ambiente pulados; dois testes SQL novos aprovados separadamente em esquema isolado. Após os ajustes finais de canonical de partido e capacidade XML, 115 testes direcionados passaram. Ruff, contrato de variáveis e revisão estrutural passaram. A checagem da versão final está em `data/seo/final-html-check-20261102.json`.
