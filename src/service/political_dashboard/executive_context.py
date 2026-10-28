"""Display government support evidence without presenting it as personal affiliation."""

from service.public_profile_web.security import official_url, text


def render_government_context_observations(observations):
    if not observations:
        return ""
    rows = []
    for record in observations:
        source = official_url(record.get("source_url"))
        link = (
            f'<a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
            'Ler fonte do contexto ↗</a>' if source else ""
        )
        rows.append(
            f'<li><strong>{text(record.get("date"))} · {text(record["title"])}</strong>'
            f'<p>{text(record.get("summary"))}</p>{link}</li>'
        )
    return (
        '<aside class="panorama-executive-context" aria-label="Contexto político documentado">'
        '<h4>Contexto político documentado</h4>'
        '<p>Apoio ao governo e filiação pessoal são informações diferentes.</p>'
        f'<ul>{"".join(rows)}</ul></aside>'
    )
