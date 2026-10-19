# Publicação estática do guia de cargos

O guia é exportado sem banco, credenciais ou JavaScript. A pesquisa e os perfis
continuam no backend Python. Esta entrega prepara a publicação; não cria conta,
não publica o site e não comprova capacidade para milhões de acessos.

## Gerar o pacote

Na raiz do projeto:

```bash
.venv/bin/se-liga-brasil build-static-site --output-directory dist/public
```

Para um frontend em domínio separado, informe a origem HTTPS real do backend:

```bash
.venv/bin/se-liga-brasil build-static-site --output-directory dist/public --backend-origin https://api.seu-dominio.com
```

O domínio acima é ilustrativo. O comando não acessa rede nem banco. Sem
`--backend-origin`, `/pessoas` precisa ser encaminhado ao backend pelo mesmo
host/proxy. Publicar apenas o guia sem esse encaminhamento deixa a pesquisa
indisponível. Não publicar diretórios de dados, arquivos de ambiente ou o projeto inteiro.

## Conteúdo de dist/public

- `index.html` e `como-funciona/index.html`: entrada municipal.
- `como-funciona/{municipal,estadual,federal,distrital,todos}/index.html`:
  cinco páginas prontas; filtros são links entre arquivos, sem execução Python.
- `assets/*.HASH.css`: estilos com hash do conteúdo; cache imutável por um ano.
- `*.gz`: representações gzip determinísticas para hosts que suportem gzip estático.
- `_headers`: regras declarativas compatíveis com Netlify/Cloudflare Pages.
- `manifest.json`: arquivos publicados, tamanhos e SHA-256; sem credenciais.

Os SVGs são incorporados no HTML e não exigem requisições adicionais.
O build é determinístico para a mesma entrada. Execute em diretório de saída
novo/limpo no CI, para não enviar artefatos antigos de builds anteriores.
Custo de build O(total de bytes gerados), com cinco variantes fixas.

## Cache e compressão

HTML: navegador por 60 segundos; cache compartilhado por uma hora;
`stale-while-revalidate` por até um dia. Alterações urgentes exigem invalidar
cache na CDN, além de publicar. CSS versionado: um ano com `immutable`.
Não renomear o conteúdo de um arquivo mantendo o mesmo hash.

O host precisa servir `.html` como HTML, `.css` como CSS e negociar gzip/Brotli
com `Vary: Accept-Encoding`. Os arquivos `.gz` por si só não ativam compressão:
Netlify/Cloudflare podem comprimir os arquivos originais automaticamente; em
outros hosts configurar o equivalente. Verificar cabeçalhos após publicação.
`_headers` não é uma configuração universal e deve ser adaptado a outros hosts.

A prévia Python também responde com gzip, ETag, `304` e regras de cache no guia
 e nos estilos. Pesquisa, perfis, APIs e erros continuam com `no-store`.
O cache gzip local tem no máximo 32 representações. Essa prévia usa servidor
local; não é o servidor de produção nem substitui CDN.

## Verificação após publicar

Confirmar as cinco esferas, estilos, navegação e formulário da pesquisa.
Inspecionar `Cache-Control`, `Content-Encoding`, `Vary`, ETag quando fornecido
pelo host, e resposta condicional. Verificar que não há fallback do tipo SPA
respondendo HTML de sucesso para rotas inexistentes. Não carregar Parquets ou
consultar o banco na página educativa. Medir latência, transferência e cache
hit antes de afirmar capacidade de tráfego.
