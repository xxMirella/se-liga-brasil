# Panorama político: quem tem a maioria? (v3)

A página `/panorama` mostra, para cada legislatura (janelas de quatro anos desde 1983-1986), qual bloco político teve a maior bancada na Câmara dos Deputados e no Senado, quem presidia o país e como isso mudou ao longo do tempo. Ela **substitui de vez** a visão territorial anterior (estado, município, ano e abordagem política). Código: `src/service/majority_panorama/`; rota: `application/public_portal.py::route_majority_panorama`; leitura: `application/majority_panorama_reader.py`.

## Seções (nesta ordem)

1. Abertura: resposta curta sobre a legislatura selecionada.
2. Linha do tempo: uma linha por casa e uma de presidentes, por período ou por bloco.
3. Período selecionado: hemiciclo, cartões por legislatura, cenários e propostas de maioria.
4. Como ler: como os partidos foram agrupados, de onde vêm os números e o que a série não cobre.

## Parâmetros da URL

Cada interação é um link (sem JavaScript). Só estes parâmetros são aceitos; qualquer outro, repetido ou inválido, devolve 400 antes de consultar o banco.

| Parâmetro | Valores | Padrão (omitido no link) |
|---|---|---|
| `leg` | primeiro ano da legislatura, só dígitos (`2019` = 2019-2022) | legislatura mais recente |
| `house` | `camara`, `senado` | `camara` |
| `mode` | `partido`, `bloco` (cor por partido ou por bloco) | `partido` |
| `hl` | bloco ou sigla de partido em destaque (até 40 caracteres) | nenhum |
| `scen` | `prop`, `conc`, `equi` (cenários de maioria) | `prop` |
| `prop` | `A`, `B` (proposta) | `B` |
| `view` | `periodo`, `bloco` (leitura da linha do tempo) | `periodo` |
| `bloc` | `left`, `center`, `right`, `far_right`, `undetermined`, `controversial`, `unaffiliated` | `right` |

A validação está em `service/majority_panorama/state.py::parse_state`; `PanoramaState.link` gera os links e omite valores padrão. `tests/test_majority_panorama_route.py` garante que todo link renderizado é aceito pela própria rota.

## Categorias separadas

Os blocos são as categorias de orientação do catálogo do projeto: Esquerda, Centro, Direita e Extrema direita (ideológicas, entram na conta do maior bloco) e três grupos neutros que **nunca** entram nessa conta nem são somados a outro bloco:

- Sem classificação: não há classificação datada para o partido no ano; isso não significa centro.
- Classificação controversa: fontes classificam o partido de formas diferentes no mesmo ano.
- Sem filiação: parlamentares sem partido.

Nenhum partido é classificado pela página; a classificação vem de `political_orientation_catalog`. Maior bloco não significa base do governo.

## Regra de "sem dados"

Período sem composição documentada aparece como "sem dados"; nada é estimado, interpolado ou tratado como centro. O mesmo vale para anos anteriores ao início da série e para casas sem composição na legislatura. Uma legislatura sem dados nas duas casas não gera conclusão; se nenhuma legislatura tem dados, a página responde 200 mas com `noindex`.

## Decisão: remoção da visão territorial

- A página não aceita mais `uf`, `year`, `level`, `territory`, `municipality_ibge`, `senate_uf` nem `view=political_orientation`; esses parâmetros devolvem 400.
- Os dados territoriais e anuais continuam existindo: `/api/political-dashboard` aceita os mesmos parâmetros de antes e alimenta o construtor do panorama. As projeções (`political_dashboard_annual` e histórico pré-calculado) não mudaram.
- Removidos: renderização do painel antigo em `service/political_dashboard/` (página, painéis, filtros territoriais, linha do tempo SVG, leitura por casa, glossário), `panorama.css`, `/assets/panorama.css`, os sitemaps `panorama-<território>.xml` e os componentes sem uso de `web_components` (ver `frontend-design-system.md`). Permanecem os módulos de dados e classificação (agregação, contratos, composição por orientação, catálogos).

## SEO e implantação

- Canônico `/panorama`; só `leg` válido gera página distinta. Detalhes em `seo-e-indexacao.md`.
- A validação de release sonda `/panorama` e `/panorama?leg=2019&house=senado` além da API (`deploy-vercel.md`).
