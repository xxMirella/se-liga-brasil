"""Reading links remain distinct from a nominal vote and from an enacted law."""

from service.public_profile_web.security import official_url, text


def render_reading_links(item):
    proposition = item.get("proposition") or {}
    fields = (
        ("voted_text_url", "Ler texto efetivamente votado"),
        ("text_url", "Ler documento publicado da proposta ou emenda"),
        ("document_url", "Consultar matéria e seus documentos"),
        ("final_norm_url", "Ler norma promulgada · texto final"),
    )
    links = []
    for field, label in fields:
        url = official_url(item.get(field) or proposition.get(field))
        if url:
            links.append(f'<a href="{text(url)}" target="_blank" '
                         f'rel="noopener noreferrer">{label} ↗</a>')
    voted = official_url(item.get("voted_text_url") or proposition.get("voted_text_url"))
    has_reading_link = bool(links)
    if not voted and item.get("action_type") in {None, "vote"}:
        links.append('<small>A versão exata do texto votado ainda não foi confirmada. '
                     'O documento publicado pode diferir da emenda, do substitutivo '
                     'ou da versão submetida à votação.</small>')
    if not has_reading_link:
        links.insert(0, '<p>Link de leitura do documento ainda não disponível.</p>')
    return '<div class="legislative-reading-links">' + "<br>".join(links) + '</div>'
