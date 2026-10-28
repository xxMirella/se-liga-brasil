"""Explain political vocabulary independently from the dated party classification algorithm."""

from service.public_profile_web.security import text

GLOSSARY_ENTRIES = ({'term': 'Esquerda',
  'definition': 'Prioriza reduzir desigualdades sociais e econômicas, com direitos '
                'trabalhistas, serviços públicos e redistribuição. Inclui correntes '
                'reformistas e anticapitalistas.',
  'source_url': 'https://www.politize.com.br/esquerda-e-direita-mitos-e-preconceitos/'},
 {'term': 'Centro',
  'definition': 'Combina propostas de esquerda e de direita, conforme o tema, e costuma '
                'preferir mudanças graduais e negociação.',
  'source_url': 'https://www.politize.com.br/espectro-politico/'},
 {'term': 'Direita',
  'definition': 'Dá maior peso à propriedade privada, à iniciativa de mercado e à preservação '
                'de instituições ou tradições. Inclui correntes liberais e conservadoras.',
  'source_url': 'https://www.politize.com.br/esquerda-e-direita-mitos-e-preconceitos/'},
 {'term': 'Extrema esquerda',
  'definition': 'Busca romper com o capitalismo. Na definição acadêmica estrita, também '
                'rejeita a democracia liberal; difere da esquerda radical que aceita a disputa '
                'democrática.',
  'source_url': 'https://library.fes.de/pdf-files/ipg/ipg-2009-1/10_a_march_us.pdf'},
 {'term': 'Extrema direita',
  'definition': 'Combina autoritarismo e nacionalismo excludente. Na definição acadêmica '
                'estrita, rejeita a democracia; não é sinônimo de toda a direita.',
  'source_url': 'https://www.sv.uio.no/c-rex/english/resources/key-consepts-and-questions/what-is-right-wing-extremism.html'},
 {'term': 'Fascismo',
  'definition': 'Ideologia de extrema direita, ultranacionalista e autoritária, que subordina '
                'direitos ao líder e à nação, combate o pluralismo e legitima a perseguição a '
                'opositores.',
  'source_url': 'https://encyclopedia.ushmm.org/content/en/article/fascism-1'},
 {'term': 'Ditadura',
  'definition': 'Regime em que uma pessoa ou grupo concentra o poder sem controle democrático '
                'efetivo, restringindo oposição e liberdades. Pode existir sob diferentes '
                'ideologias.',
  'source_url': 'https://www.politize.com.br/ditadura-o-que-e/'})


def render_orientation_glossary(data):
    if data.get("view") != "political_orientation" or not GLOSSARY_ENTRIES:
        return ""
    entries = "".join(render_glossary_entry(entry) for entry in GLOSSARY_ENTRIES)
    return f'''<aside class="panorama-orientation-glossary"
aria-labelledby="orientation-glossary-title">
<h3 id="orientation-glossary-title">Entenda os termos</h3>
<dl>{entries}</dl>
<p class="panorama-caption">São conceitos gerais, com usos diferentes na literatura.
Uma posição na escala não basta
para chamar um partido ou governo de fascista ou ditatorial.
Os termos extremos deste glossário não alteram as três faixas usadas no gráfico.</p>
</aside>'''


def render_glossary_entry(entry):
    source = (f'<a href="{text(entry["source_url"])}" target="_blank" '
              'rel="noopener noreferrer">Ler referência ↗</a>')
    return (f'<div><dt>{text(entry["term"])}</dt>'
            f'<dd>{text(entry["definition"])} {source}</dd></div>')
