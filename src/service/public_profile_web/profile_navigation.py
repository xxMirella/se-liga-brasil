"""Anchor navigation between the sections of the single-page person profile."""

from service.public_profile_web.security import person_path

PROFILE_SECTIONS = (
    ("trajetoria", "Trajetória"),
    ("presenca", "Presença"),
    ("atuacao", "Atuação"),
    ("bens", "Bens e remuneração"),
)


def render_section_navigation():
    links = "".join(f'<a href="#{anchor}">{label}</a>' for anchor, label in PROFILE_SECTIONS)
    return f'<nav class="ds-profile-sections" aria-label="Seções do perfil">{links}</nav>'


def activity_history_href(person_id):
    """Raw (unescaped) link to the full voting history, loaded only on request."""
    return person_path(person_id) + "?tab=activity&scope=history#atuacao"
