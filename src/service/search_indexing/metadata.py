"""Server-rendered search and sharing metadata using public page content only."""

import json
import os
import re
from html import escape, unescape
from urllib.parse import parse_qsl, urlsplit

from service.search_indexing.canonical import canonical_page
from service.search_indexing.configuration import public_site_origin, search_indexing_enabled

DESCRIPTIONS = {
    "/": ("Conheça trajetórias públicas, partidos e atuação política no Brasil, "
          "com dados oficiais, fontes e cobertura documentada."),
    "/pessoas": ("Consulte perfis públicos, cargos, filiações, bens declarados e atuação "
                 "parlamentar com referência às fontes oficiais."),
    "/como-funciona": ("Entenda os cargos públicos, as responsabilidades e as diferenças "
                       "entre os poderes municipal, estadual e federal."),
    "/fontes-dos-dados": ("Consulte as fontes, os critérios de cobertura e a metodologia "
                          "dos dados públicos apresentados pelo Se Liga, Brasil."),
    "/comparacao-de-classificacoes": ("Compare classificações de partidos por pesquisas "
                                     "de especialistas e evidências de atuação, "
                                     "com metodologia e limitações explícitas."),
}


def panorama_search_text(target):
    from service.majority_panorama.legislature_windows import LegislatureWindow
    from service.majority_panorama.state import parse_state

    state = parse_state(dict(parse_qsl(urlsplit(target).query)))
    scope = ""
    if state.legislature_id:
        scope = " · Legislatura " + LegislatureWindow(int(state.legislature_id)).label
    description = (
        "Veja, legislatura por legislatura, quem teve a maioria na Câmara dos Deputados e no "
        "Senado: bancadas por partido e por bloco, linha do tempo, presidentes e "
        "cobertura documentada, com fontes e limites explícitos."
    )
    return "Panorama político: quem tem a maioria?" + scope + " · Se Liga, Brasil", description


def page_search_text(target, original_title, today):
    path = urlsplit(target).path.rstrip("/") or "/"
    if path == "/panorama":
        return panorama_search_text(target)
    if path.startswith("/pessoas/"):
        name = original_title.removesuffix(" · Se Liga, Brasil")
        activity = dict(parse_qsl(urlsplit(target).query)).get("tab") == "activity"
        title = name + (" · Atuação parlamentar" if activity else " · Perfil público")
        return title + " · Se Liga, Brasil", (
            f"Consulte a trajetória pública de {name}: vínculos, bens declarados e atuação "
            "documentada, com referência às fontes oficiais e à cobertura disponível."
        )
    description = DESCRIPTIONS.get("/" if path == "/sobre" else path, DESCRIPTIONS["/"])
    if path == "/como-funciona":
        sphere = dict(parse_qsl(urlsplit(target).query)).get("esfera", "municipal")
        labels = {"municipal": "Cargos municipais", "estadual": "Cargos estaduais",
                  "federal": "Cargos federais", "distrital": "Cargos do Distrito Federal",
                  "todos": "Cargos públicos no Brasil"}
        original_title = labels[sphere] + " · Responsabilidades · Se Liga, Brasil"
    if path == "/comparacao-de-classificacoes":
        party = dict(parse_qsl(urlsplit(target).query)).get("partido")
        if party:
            original_title = f"{party} · Comparação de classificações · Se Liga, Brasil"
    return original_title, description


def structured_page(title, description, canonical):
    origin = public_site_origin()
    website = {"@type": "WebSite", "@id": origin + "/#website",
               "url": origin + "/", "name": "Se Liga, Brasil", "inLanguage": "pt-BR"}
    page = {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical,
            "name": title, "description": description, "inLanguage": "pt-BR",
            "isPartOf": {"@id": website["@id"]}}
    if "/pessoas/" in canonical:
        page["mainEntity"] = {"@type": "Person", "name": title.split(" · ", 1)[0],
                              "url": canonical.split("?", 1)[0]}
    data = json.dumps({"@context": "https://schema.org", "@graph": [website, page]},
                      ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    return '<script type="application/ld+json">' + data + '</script>'


def render_search_metadata(title, description, canonical, *, noindex=False):
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large"
    metadata = [('name', 'description', description), ('name', 'robots', robots),
                ('property', 'og:type', 'website'), ('property', 'og:locale', 'pt_BR'),
                ('property', 'og:site_name', 'Se Liga, Brasil'), ('property', 'og:title', title),
                ('property', 'og:description', description), ('property', 'og:url', canonical),
                ('name', 'twitter:card', 'summary'), ('name', 'twitter:title', title),
                ('name', 'twitter:description', description)]
    if token := os.environ.get("GOOGLE_SITE_VERIFICATION"):
        metadata.append(('name', 'google-site-verification', token))
    tags = "\n".join(f'<meta {kind}="{key}" content="{escape(value, quote=True)}">'
                     for kind, key, value in metadata)
    return (tags + '\n<link rel="canonical" href="' + escape(canonical, quote=True) + '">'
            + structured_page(title, description, canonical))


def enrich_public_html(body, target, today, status=200, *, indexable=True):
    html = body.decode("utf-8")
    if status != 200:
        return html.replace('</head>', '<meta name="robots" content="noindex, follow"></head>', 1)
    head = html.partition('</head>')[0]
    match = re.search(r'<title>(.*?)</title>', head, flags=re.DOTALL)
    if match is None:
        return html
    title, description = page_search_text(target, unescape(match[1]), today)
    canonical, filtered = canonical_page(target, today)
    html = html.replace(match[0], '<title>' + escape(title) + '</title>', 1)
    metadata = render_search_metadata(title, description, public_site_origin() + canonical,
                                      noindex=filtered or not indexable
                                      or not search_indexing_enabled())
    return html.replace('</head>', metadata + '</head>', 1)
