"""Public identity: portrait, name, office, party and tenure chips (reference: Perfil v2)."""

from itertools import islice

from service.public_profile_web.brazilian_states import UF_NAMES
from service.public_profile_web.profile_dates import format_full_date, format_month_year
from service.public_profile_web.security import official_url, text

LOWERCASE_NAME_WORDS = frozenset({"da", "das", "de", "do", "dos", "e"})

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


def title_case_name(value):
    """Registered names are upper case; display them as 'Erika Hilton' without losing initials."""
    words = str(value or "").lower().split()
    return " ".join(
        word if index and word in LOWERCASE_NAME_WORDS else word.capitalize()
        for index, word in enumerate(words)
    )


def render_portrait(profile):
    photo = profile.get("photo") or {}
    url = official_url(photo.get("url"))
    if not url:
        return (
            '<div class="ds-profile-portrait ds-profile-portrait--empty" role="img" '
            'aria-label="Foto não disponível"><span aria-hidden="true">◯</span></div>'
        )
    name = text(title_case_name(profile.get("display_name")), "pessoa")
    attribution = photo.get("attribution")
    caption = f"<small>{text(attribution)}</small>" if attribution else ""
    return (
        f'<div class="ds-profile-portrait"><img src="{text(url)}" '
        f'alt="Foto institucional de {name}" width="120" height="150" '
        f'referrerpolicy="no-referrer">{caption}</div>'
    )


def render_political_party(profile):
    political_party = profile.get("political_party") or {}
    abbreviation = political_party.get("abbreviation")
    if not abbreviation:
        return "Partido não disponível"
    name = political_party.get("name")
    full_name = (
        f' <span>({text(title_case_name(name))})</span>' if name and name != abbreviation else ""
    )
    return f"<strong>{text(abbreviation)}</strong>{full_name}"


def office_line(office):
    label = OFFICE_LABELS.get(office.get("office_kind"), "Cargo público")
    uf_name = UF_NAMES.get(office.get("represented_uf"))
    if uf_name:
        return f"{label} por {uf_name}"
    institution = (office.get("institution") or {}).get("name")
    return f"{label} · {text(institution)}" if institution else label


def render_observed_office(status):
    if status.get("office_kind"):
        reference = text(status.get("observed_on"))
        return [
            f"{office_line(status)}<br>Cargo observado em {reference}; exercício atual não "
            "confirmado."
        ]
    if status.get("has_current_public_office") is False and status.get("status") == "observed":
        return ["Não ocupa cargo público atual, segundo a evidência disponível"]
    return ["Sem cargo público atual confirmado"]


def render_offices(profile):
    """One subtitle paragraph per office; the party closes the last one."""
    offices = list(islice(profile.get("current_offices", []), 20))
    lines = [office_line(office) for office in offices] or render_observed_office(
        profile.get("public_office") or {}
    )
    lines[-1] += f" · {render_political_party(profile)}"
    return "".join(f'<p class="ds-profile-identity__office">{line}</p>' for line in lines)


def render_chip(content):
    return f'<span class="ds-profile-chip">{content}</span>'


def render_remaining_term(office):
    remaining = office.get("remaining_term") or {}
    last_day = format_full_date(remaining.get("last_day"))
    if remaining.get("status") != "documented_term_boundary" or not last_day:
        return render_chip("Término do mandato não informado")
    if office.get("capacity") == "substitute":
        return render_chip(f"Mandato previsto até {last_day}; a suplência pode terminar antes")
    return render_chip(f"Mandato termina em {last_day}")


def render_tenure_chip(office):
    since = format_month_year(office.get("starts_on"))
    if not since:
        return ""
    substitute = office.get("capacity") == "substitute"
    verb = "Em exercício como suplente" if substitute else "Em exercício"
    return render_chip(f"{verb} desde {since}")


def render_tenures(profile):
    chips = ""
    for office in islice(profile.get("current_offices", []), 20):
        chips += render_tenure_chip(office) + render_remaining_term(office)
    return chips


def render_person_facts(profile):
    age = (profile.get("age") or {}).get("value")
    education = profile.get("education_level")
    facts = [f"{text(age)} anos"] if age is not None else []
    if education:
        facts.append(text(str(education).lower()))
    return render_chip(" · ".join(facts)) if facts else ""


def render_profile_header(profile):
    chips = render_tenures(profile) + render_person_facts(profile)
    chip_list = f'<div class="ds-profile-chips">{chips}</div>' if chips else ""
    name = text(title_case_name(profile.get("display_name")), "Perfil público")
    return (
        '<section class="ds-profile-identity" aria-label="Identidade">'
        f'{render_portrait(profile)}<div class="ds-profile-identity__body">'
        f'<span class="ds-profile-identity__eyebrow">Perfil público</span><h1>{name}</h1>'
        f"{render_offices(profile)}{chip_list}</div></section>"
    )
