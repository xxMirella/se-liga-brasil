"""Portal sections shown in the header menu; a section key marks the current page."""

PORTAL_SECTIONS = (
    ("about", "Sobre", "/sobre"),
    ("people", "Consulta de pessoas", "/pessoas"),
    ("panorama", "Panorama político", "/panorama"),
    ("guide", "Entenda os cargos", "/como-funciona"),
    ("sources", "Fontes dos dados", "/fontes-dos-dados"),
)


def render_site_navigation(active_section):
    links = "".join(
        f'<a class="ds-site-nav__link" href="{url}"'
        + (' aria-current="page"' if key == active_section else "")
        + f">{label}</a>"
        for key, label, url in PORTAL_SECTIONS
    )
    return (
        '<nav class="ds-site-nav" aria-label="Principal">'
        f'<div class="ds-container ds-site-nav__list">{links}</div></nav>'
    )
