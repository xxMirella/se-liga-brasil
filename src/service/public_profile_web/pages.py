"""Compose server-rendered pages exclusively from public service projections."""

from service.public_profile_web.activity_section import ACTIVITY_SCRIPT, render_activity_section
from service.public_profile_web.layout import render_layout
from service.public_profile_web.page_heading import render_page_heading
from service.public_profile_web.profile import render_profile_header, title_case_name
from service.public_profile_web.profile_assets_section import render_assets_section
from service.public_profile_web.profile_attendance import render_attendance_section
from service.public_profile_web.profile_career import render_career_section
from service.public_profile_web.profile_dates import format_full_date
from service.public_profile_web.profile_navigation import render_section_navigation
from service.public_profile_web.profile_summary import render_profile_summary
from service.public_profile_web.security import text
from web_components import SCROLL_REVEAL_SCRIPT, render_link_button


def render_breadcrumb(profile):
    name = text(title_case_name(profile.get("display_name")), "Perfil")
    return (
        '<nav class="ds-profile-breadcrumb" aria-label="Você está em">'
        f'<a href="/pessoas">Consulta de pessoas</a> / {name}</nav>'
    )


def render_source_footer_note(profile):
    consulted = format_full_date(profile.get("as_of"))
    parts = [f"Consulta em {consulted}"] if consulted else []
    if profile.get("display_name"):
        parts.append(f"Nome registrado na fonte: {text(profile['display_name'])}")
    if not parts:
        return ""
    return f'<span class="ds-site-footer__note">{" · ".join(parts)}</span>'


def render_person_profile(profile, votes, filters):
    sections = (
        render_career_section(profile),
        render_attendance_section(profile),
        render_activity_section(profile, votes, filters),
        render_assets_section(profile),
    )
    content = (
        render_breadcrumb(profile) + render_profile_header(profile)
        + render_profile_summary(profile) + render_section_navigation() + "".join(sections)
    )
    return render_layout(
        title_case_name(profile.get("display_name")) or "Perfil público", content,
        workspace_class="workspace ds-profile-workspace",
        scripts=(SCROLL_REVEAL_SCRIPT, ACTIVITY_SCRIPT),
        footer_notes_html=render_source_footer_note(profile),
    )


def render_error_page(status, message="A consulta não pôde ser concluída. Tente novamente."):
    content = render_page_heading("Consulta pública", "Consulta indisponível", message) + (
        f'<p class="error-code">Código {text(status)}</p>'
        + render_link_button("Voltar à busca", "/pessoas")
    )
    return render_layout("Consulta indisponível", content)
