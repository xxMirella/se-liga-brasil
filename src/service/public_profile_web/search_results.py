"""Markup of the people search result list: cards, count, empty state and pagination."""

import re
from zlib import crc32

from service.public_profile_web.security import person_path, text

AVATAR_HUE_BUCKETS = 12
INITIALS_LENGTH = 2
TITLE_PREFIX = re.compile(
    r"^(Dr\.|Dra\.|Delegad[oa]|Pastor|Professora|Sargento|Astronauta)\s+"
)


def person_initials(name):
    words = TITLE_PREFIX.sub("", str(name or "").strip()).split()
    significant = [word for word in words if len(word) > 2 or word[:1].isupper()]
    return "".join(word[0] for word in significant[:INITIALS_LENGTH]).upper()


def avatar_hue_class(name):
    bucket = crc32(str(name or "").encode("utf-8")) % AVATAR_HUE_BUCKETS
    return f"ds-people-avatar--hue-{bucket}"


def office_label(person):
    office = person.get("current_office") or {}
    return office.get("label") if isinstance(office, dict) else office


def render_person_avatar(name):
    initials = text(person_initials(name), "")
    return (
        f'<span class="ds-people-avatar {avatar_hue_class(name)}" aria-hidden="true">'
        f"{initials}</span>"
    )


def render_search_result(person):
    path = person_path(person["person_id"])
    name = text(person.get("display_name"))
    label = office_label(person)
    office = f'<span class="ds-people-card__office">{text(label)}</span>' if label else ""
    return (
        '<li class="ds-people-item">'
        f'<a class="ds-people-card" href="{path}">'
        f"{render_person_avatar(person.get('display_name'))}"
        '<span class="ds-people-card__body">'
        f'<strong class="ds-people-card__name">{name}</strong>{office}'
        '<span class="ds-visually-hidden">Consultar perfil</span>'
        "</span></a></li>"
    )


def render_result_count(count):
    noun = "pessoa" if count == 1 else "pessoas"
    return (
        '<div class="ds-people-summary">'
        f'<strong role="status" class="ds-people-summary__count">'
        f"Mostrando {count} {noun}</strong>"
        "</div>"
    )


def render_empty_state(has_filters):
    if not has_filters:
        return (
            '<li class="ds-people-empty">'
            '<strong class="ds-people-empty__title">Busque uma pessoa pelo nome.</strong></li>'
        )
    return (
        '<li class="ds-people-empty">'
        '<strong class="ds-people-empty__title">'
        "Nenhuma pessoa encontrada para estes filtros.</strong>"
        '<p class="ds-people-empty__hint">Confira a grafia do nome ou remova um filtro. '
        "A busca ignora acentos e maiúsculas.</p>"
        '<div><a class="ds-people-empty__action" href="/pessoas">Limpar filtros</a></div></li>'
    )


def render_next_page(url, page_size):
    return (
        '<nav class="ds-people-pagination" aria-label="Paginação">'
        f'<a class="ds-people-pagination__next" href="{url}" data-people-more>'
        f"Mostrar mais {page_size}</a></nav>"
    )
