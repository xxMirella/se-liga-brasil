"""Explicit year-end name alignment to the 2018 survey; mergers never inherit scores."""

HISTORICAL_IDENTITY_POLICY = "camara_2010_2019.v2"
IDENTITY_ALIGNMENTS = {
    (2018, "PATRI"): {
        "reference_abbreviation": "PATRIOTA", "effective_on": "2018-04-26",
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2018/Abril/"
                      "aprovada-alteracao-do-nome-do-partido-ecologico-nacional-pen",
    },
    (2019, "PL"): {
        "reference_abbreviation": "PR", "effective_on": "2019-05-07",
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2019/Maio/"
                      "aprovada-alteracao-do-nome-do-partido-da-republica-pr-para-partido-liberal-pl",
    },
    (2019, "REPUBLICANOS"): {
        "reference_abbreviation": "PRB", "effective_on": "2019-08-15",
        "source_url": "https://www.tse.jus.br/partidos/partidos-registrados-no-tse/republicanos",
    },
    (2019, "CIDADANIA"): {
        "reference_abbreviation": "PPS", "effective_on": "2019-09-19",
        "source_url": "https://www.tse.jus.br/comunicacao/noticias/2019/Setembro/"
                      "plenario-aprova-mudanca-do-nome-do-pps-para-cidadania",
    },
}


def chamber_survey_identity(abbreviation, year, reference, enabled):
    if not enabled or reference != 2018:
        return abbreviation, None
    alignment = IDENTITY_ALIGNMENTS.get((year, abbreviation.upper()))
    if alignment is None:
        return abbreviation, None
    return alignment["reference_abbreviation"], dict(alignment)
