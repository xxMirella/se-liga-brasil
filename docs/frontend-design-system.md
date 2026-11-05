# Frontend: design system e componentes reutilizáveis

Biblioteca: `src/web_components/` (biblioteca reutilizável, sem rede nem banco; JavaScript só como melhoria progressiva). Design de referência: protótipo "Panorama v2" (arquivo `Panorama v2.dc.html`, linguagem de template com estilos inline; os valores foram portados para tokens e classes `ds-*`). A página `/panorama` atual (v3, nacional por legislatura) é construída só com estes componentes.

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `assets/design-tokens.css` | variáveis (cores, fontes, raios, largura) |
| `assets/design-system.css` | base, shell (header, menu, footer) e componentes `ds-*` |
| `assets/majority-components*.css` | estilo das primitivas do panorama (barras, legendas, hemiciclo, linha do tempo, período) |
| `site_header.py`, `navigation.py`, `site_footer.py` | header com busca e menu sem JS (`<details>`), seções do portal, footer |
| `page_shell.py` | documento completo: `render_page(title, content_html, active_section=...)` |
| `elements.py` | eyebrow, hero, section, card, notice, botão-link, chip, abas e segmentado por link, disclosure |
| `static_text.py` | leitura de texto empacotado com cache por versão do arquivo |

`service/public_profile_web/layout.py::render_layout` é o adaptador das páginas existentes: mesma assinatura, agora sobre `render_page`. `public_stylesheet()` entrega `design-tokens + design-system + public-profile.css`.

## Regras

- **Sem estilo inline.** A política de segurança é `style-src 'self'` (`application/vercel.py`, `static_publication/build.py`); `style="..."` é bloqueado. Toda aparência vai para classes em CSS.
- **JavaScript é melhoria progressiva** (autorizado pela usuária; ver `AGENTS.md`). Toda interação funciona como link, formulário GET, `<details>` e `:target`, e a URL guarda o estado. Os scripts em `assets/*.js` (`panorama-enhance.js`) só deixam a experiência mais suave: filtros sem recarregar a página e revelação ao rolar quando o navegador não tem `animation-timeline`. Sem `<script>` inline e sem dependências.
- **Sem fontes externas.** `--font-display/body/mono` têm pilhas de fallback locais; o CSP não permite Google Fonts.
- Texto de argumento é escapado pelos componentes; argumentos `*_html` são marcação confiável.
- Estilo específico de página fica no CSS da página (`civic-education.css`, `party-comparison.css`, `public-profile.css`). O que se repetir em duas páginas é promovido para `web_components`.
- Nomes em inglês, funções com uma responsabilidade (limites do `AGENTS.md`).

## Primitivas do panorama (v3)

Todas são funções puras que devolvem HTML; cores e alturas variam por classe (`ds-bloc--*`, classes de dezena e unidade), nunca por `style`. Estado de interação é sempre um link.

| Primitiva | Arquivo | Uso |
|---|---|---|
| `render_stacked_bar` / `BarSegment` | `stacked_bar.py` | barra empilhada como tabela de uma linha (larguras por `<col>`), com marcador opcional de metade; `bloc_class_suffix` converte a chave do bloco em sufixo de classe |
| `render_choice_links` / `ChoiceLink` | `choice_links.py` | escolha única por links (casa, modo de cor, cenário, proposta); a opção atual leva `aria-current` |
| `render_bloc_legend`, `render_bloc_swatch` | `bloc_legend.py` | legenda e amostra de cor por bloco (ou qualquer categoria com classe `ds-bloc--*`) |
| `render_dot_grid` | `dot_grid.py` | grade de pontos iguais, um por unidade (por exemplo, 100 cadeiras), coloridos por bloco |
| `render_column_chart` / `ChartColumn` | `column_chart.py` | gráfico de colunas cujas colunas são links; altura por classes de dezena e unidade |
| `render_parliament_chart` / `SeatGroup`, `seat_fills` | `parliament_chart.py` | hemiciclo em SVG, um `<circle>` por cadeira, com destaque de grupo |
| `parliament_seat_positions`, `SeatPosition`, `canvas_point` | `parliament_layout.py` | geometria pura do hemiciclo (fileiras concêntricas), sem partidos, cores ou HTML |

Foram removidos os componentes do painel territorial antigo que nenhuma página usa mais: `filter_bar`, `seat_grid`, `bar_list`, `anchor_tabs`, `period_picker`, `member_cards`, `tones` e o CSS `data-components.css`. Se uma página futura precisar de algo equivalente, a primitiva nova deve nascer em `web_components` com teste.
