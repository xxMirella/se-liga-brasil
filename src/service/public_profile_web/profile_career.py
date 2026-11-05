"""Career timeline section of the person profile (reference: Perfil v2, "Trajetória")."""

from service.public_profile_web.security import text

OFFICE_LABELS = {
    "federal_deputy": "Deputado(a) federal",
    "state_deputy": "Deputado(a) estadual",
    "district_deputy": "Deputado(a) distrital",
    "senator": "Senador(a)",
    "councillor": "Vereador(a)",
    "mayor": "Prefeito(a)",
    "vice_mayor": "Vice-prefeito(a)",
    "governor": "Governador(a)",
    "vice_governor": "Vice-governador(a)",
    "senator_substitute": "Suplente de senador(a)",
    "other": "Outro cargo público",
}
MAXIMUM_TIMELINE_ENTRIES = 20


def render_career_period(office):
    start_year = str(office.get("starts_on") or "")[:4]
    return f"{text(start_year)} – hoje" if start_year else "Início não confirmado"


def render_career_summary(office, party_abbreviation):
    parts = [party_abbreviation, (office.get("institution") or {}).get("name")]
    labels = [text(part) for part in parts if part]
    labels.append("em exercício como suplente" if office.get("capacity") == "substitute"
                  else "em exercício")
    return " · ".join(labels)


def render_career_entry(office, party_abbreviation, *, first, last):
    label = OFFICE_LABELS.get(office.get("office_kind"), "Cargo público")
    uf = office.get("represented_uf")
    title = f"{label} · {text(uf)}" if uf else label
    marker_class = "ds-profile-career__dot" + ("" if first else " ds-profile-career__dot--past")
    connector = "" if last else '<span class="ds-profile-career__line"></span>'
    return (
        '<li class="ds-profile-career__entry">'
        f'<span class="ds-profile-career__period">{render_career_period(office)}</span>'
        f'<span class="ds-profile-career__track"><span class="{marker_class}"></span>'
        f"{connector}</span>"
        '<div class="ds-profile-career__body">'
        f'<strong class="ds-profile-career__title">{title}</strong>'
        f'<span class="ds-profile-career__summary">'
        f"{render_career_summary(office, party_abbreviation)}</span></div></li>"
    )


def render_career_fallback(profile):
    status = profile.get("public_office") or {}
    if status.get("office_kind"):
        label = OFFICE_LABELS.get(status["office_kind"], "Cargo público")
        institution = (status.get("institution") or {}).get("name")
        return (
            f'<p class="ds-profile-career__note">{label} · {text(institution)}. '
            f"Cargo observado em {text(status.get('observed_on'))}; "
            "exercício atual não confirmado.</p>"
        )
    return '<p class="ds-profile-career__note">Nenhum cargo público atual confirmado.</p>'


def render_career_section(profile):
    offices = sorted(
        profile.get("current_offices", [])[:MAXIMUM_TIMELINE_ENTRIES],
        key=lambda office: str(office.get("starts_on") or ""),
        reverse=True,
    )
    party = (profile.get("political_party") or {}).get("abbreviation")
    entries = "".join(
        render_career_entry(office, party, first=index == 0, last=index == len(offices) - 1)
        for index, office in enumerate(offices)
    )
    body = (
        f'<ol class="ds-profile-career__list">{entries}</ol>' if entries
        else render_career_fallback(profile)
    )
    return (
        '<section id="trajetoria" class="ds-profile-career" aria-labelledby="trajetoria-title">'
        '<h2 id="trajetoria-title" class="ds-profile-heading">Trajetória</h2>'
        f"{body}"
        '<p class="ds-profile-career__note">Cargos anteriores ainda não constam na base '
        "do Se Liga; a ausência não indica que não existiram.</p></section>"
    )
