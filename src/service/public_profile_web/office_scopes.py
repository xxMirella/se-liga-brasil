"""Show documented powers and restrictions without assessing personal performance."""

from itertools import islice

from service.public_profile_web.profile import OFFICE_LABELS
from service.public_profile_web.security import official_url, text


def render_scope_sources(sources):
    links = []
    for source in islice(sources or [], 20):
        url = official_url(source.get("url"))
        if url:
            reference = " · " + text(source["reference"]) if source.get("reference") else ""
            links.append(
                f'<a href="{text(url)}" target="_blank" rel="noopener noreferrer">'
                f"{text(source.get('title'), 'Fonte oficial')}{reference}</a>"
            )
    return " · ".join(links)


def render_scope_items(title, items):
    rows = []
    for item in islice(items or [], 50):
        scope = (
            "Aplicação individual" if item.get("scope") == "individual" else "Competência do órgão"
        )
        rows.append(
            f"<li><strong>{text(item.get('title'))}</strong> "
            f"{text(item.get('description'), '')} "
            f"<small>{scope}</small> "
            f"{render_scope_sources(item.get('sources'))}</li>"
        )
    return f"<h4>{title}</h4><ul>" + "".join(rows) + "</ul>" if rows else ""


def relevant_scope_keys(profile, votes, filters):
    selected = filters.get("office_kind") or filters.get("exercise_id")
    exercises = votes.get("exercises", []) if selected else profile.get("current_offices", [])
    keys = set()
    for exercise in islice(exercises, 100):
        if filters.get("office_kind") and exercise.get("office_kind") != filters["office_kind"]:
            continue
        if filters.get("exercise_id") and str(exercise.get("exercise_id")) != str(
            filters["exercise_id"]
        ):
            continue
        kind = exercise.get("office_kind")
        jurisdiction = "BR"
        if kind in {"state_deputy", "governor", "vice_governor"}:
            jurisdiction = exercise.get("represented_uf")
        elif kind == "district_deputy":
            jurisdiction = "DF"
        keys.add((kind, jurisdiction))
    return keys


def render_office_scopes(profile, votes=None, filters=None):
    filters = filters or {}
    relevant = relevant_scope_keys(profile, votes or {}, filters)
    scopes = [
        scope
        for scope in islice(profile.get("legal_scopes") or [], 30)
        if (scope.get("office_kind"), scope.get("jurisdiction")) in relevant
    ]
    if not scopes:
        return (
            '<details class="duties"><summary>Competências e limites do cargo</summary>'
            "<p>O enquadramento legal deste cargo ainda não está disponível.</p></details>"
        )
    sections = []
    for scope in scopes:
        label = OFFICE_LABELS.get(scope.get("office_kind"), "Cargo público")
        limitations = "".join(
            f"<li>{text(value)}</li>" for value in islice(scope.get("limitations", []), 30)
        )
        sections.append(
            f"<section><h3>{label} · {text(scope.get('jurisdiction'))}</h3>"
            + "<p>Síntese documental; a vigência jurídica histórica precisa de verificação.</p>"
            + render_scope_items("Competências", scope.get("competencies"))
            + render_scope_items("Limites de atuação", scope.get("restrictions"))
            + f"<ul>{limitations}</ul>"
            + render_scope_sources(scope.get("sources"))
            + "</section>"
        )
    return (
        '<details class="duties"><summary>Competências e limites do cargo</summary>'
        "<p>Enquadramento do cargo atual documentado ou do exercício selecionado no filtro.</p>"
        "<p>Competências coletivas do órgão não são decisões individuais. A quantidade de "
        "votos não mede, isoladamente, o cumprimento das atribuições.</p>"
        + "".join(sections)
        + "</details>"
    )
