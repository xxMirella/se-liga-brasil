"""Document institutional absence separately from missing ideological research."""

CONGRESS_HISTORY_URL = (
    "https://www.congressonacional.leg.br/institucional/sobre-o-congresso-nacional"
)


def documented_legislative_absence(institution_code, year):
    """1937 is a transition year; only complete closed years receive this status."""
    if institution_code not in {"camara", "senado"} or not 1938 <= year <= 1945:
        return None
    return {
        "label": "Parlamento não instalado · Estado Novo",
        "color": "#8c9990", "state": "suspended",
        "qualifier": "ausência institucional documentada",
        "detail": "O Parlamento previsto em 1937 não foi instalado; o Congresso "
                  "reabriu em 1946. Ausência de Parlamento não é posição de centro "
                  "nem classificação ideológica do governo.",
        "source_evidence": [{
            "source_url": CONGRESS_HISTORY_URL,
            "source_title": "Congresso Nacional · Breve história do Congresso Nacional",
            "source_publication_year": "não informado", "accessed_on": "2026-10-28",
            "scope": "institutional_status", "full_year_start": 1938,
            "full_year_end": 1945,
            "evidence_locator": "A Constituição de 1937 — O Parlamento Nacional fechado",
        }],
    }
