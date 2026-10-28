"""Source-confirmed interim service, independent from party and mandate duration."""

from copy import deepcopy

from service.presidential_history.reviewed_exercises import acquire_reviewed_exercise_source

REVIEWED_INTERIM_EXERCISES = (
    (
        "arquivo-nacional-president:184", {"1961-08-25", "1964-04-02"},
        "https://www2.camara.leg.br/a-camara/conheca/historia/Ex_presidentesCD_Republica/ranieri.html",
        "Assumiu interinamente a Presidência da República em vários momentos entre 1960 e 1964.",
    ),
    (
        "arquivo-nacional-president:206", {"1918-11-15"},
        "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/206-delfim-moreira-da-costa-ribeiro",
        "Delfim Moreira assumiu interinamente a presidência da República.",
    ),
    (
        "arquivo-nacional-president:195", {"1955-11-08"},
        "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/assuntos/biografias/195-carlos-coimbra-da-luz",
        "Carlos Luz assumiu interinamente a presidência da República em 8 de novembro",
    ),
)


def enrich_documented_exercise_capacity(acquisition, exercises):
    enriched = deepcopy(exercises)
    for person_id, starts, url, locator in REVIEWED_INTERIM_EXERCISES:
        matching = [row for row in enriched if row["person_id"] == person_id
                    and row["starts_on"] in starts]
        if not matching:
            continue
        _, evidence = acquire_reviewed_exercise_source(acquisition, url, locator)
        for exercise in matching:
            exercise["exercise_capacity"] = "acting_president"
            exercise["exercise_capacity_evidence"] = [evidence]
    return enriched
