"""Builds the `MajorityPanorama` from a `PanoramaSource`. Pure: no network, no database."""

from service.majority_panorama.composition_notes import format_brazilian_date
from service.majority_panorama.composition_source import (
    PanoramaSource,
    build_house_composition,
)
from service.majority_panorama.contracts import Legislature, MajorityPanorama
from service.majority_panorama.legislature_windows import legislature_windows
from service.majority_panorama.presidents import build_presidential_terms

HOUSE_LABELS = {"camara": "Câmara", "senado": "Senado"}


def build_legislature(window, source, today):
    return Legislature(
        legislature_id=window.legislature_id,
        first_year=window.first_year,
        end_year_exclusive=window.end_year_exclusive,
        label=window.label,
        camara=build_house_composition("camara", window, source, today),
        senado=build_house_composition("senado", window, source, today),
    )


def latest_observation(legislatures, house):
    dates = [
        getattr(legislature, house).observed_on
        for legislature in legislatures
        if getattr(legislature, house) and getattr(legislature, house).observed_on
    ]
    return max(dates, default=None)


def sources_note(legislatures):
    observed = []
    for house in ("senado", "camara"):
        day = latest_observation(legislatures, house)
        if day:
            observed.append(f"{HOUSE_LABELS[house]} em {format_brazilian_date(day)}")
    latest = "; observação mais recente: " + ", ".join(observed) if observed else ""
    return (
        "Composições anuais por partido registradas no banco do projeto a partir dos dados "
        "abertos oficiais da Câmara e do Senado" + latest + ". Presidentes: Arquivo Nacional, "
        "com partido atribuído ao mandato. Blocos: classificação datada de partidos do projeto "
        "(Câmara e Senado) e síntese revisada do governo (presidentes)."
    )


def missing_data_note(legislatures, house):
    missing = [item.label for item in legislatures if getattr(item, house) is None]
    if not missing:
        return None
    return f"{HOUSE_LABELS[house]} sem composição verificada: {', '.join(missing)}."


def coverage_notes(legislatures):
    notes = [
        "Cada legislatura mostra um único ano de referência por Casa: o último ano com "
        "composição verificada (na legislatura em curso, o dado mais recente).",
        "Períodos sem composição confiável (menos de 90% das cadeiras documentadas) aparecem "
        "como sem dados; nada é estimado.",
        "A classificação de partidos vale para o ano pesquisado; sem classificação datada, "
        "as cadeiras ficam em Sem classificação.",
        "O bloco do presidente é do governo, não do partido, e não resume o Congresso.",
    ]
    notes.extend(
        note for house in ("camara", "senado")
        if (note := missing_data_note(legislatures, house))
    )
    return tuple(notes)


def build_majority_panorama(source: PanoramaSource, today):
    legislatures = tuple(
        build_legislature(window, source, today) for window in legislature_windows(today)
    )
    return MajorityPanorama(
        legislatures=legislatures,
        presidents=build_presidential_terms(source.presidency(), today),
        generated_on=today,
        sources_note=sources_note(legislatures),
        coverage_notes=coverage_notes(legislatures),
    )
