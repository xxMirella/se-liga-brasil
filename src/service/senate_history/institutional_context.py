"""Institutional absence is distinct from missing affiliation evidence."""

from service.political_dashboard_dataset.aggregation import build_annual_partition

CLOSED_SENATE_YEARS = frozenset((*range(1931, 1935), *range(1938, 1946)))
SENATE_CLOSURE_EVIDENCE = {
    "url": "https://www12.senado.leg.br/noticias/infomaterias/2026/09/"
           "todas-as-eleicoes-para-o-senado-na-historia-da-republica",
    "source_kind": "reviewed_official_institutional_history",
    "locator": "Constituição de 1934 e Estado Novo; Fim do Estado Novo e redemocratização",
    "reviewed_on": "2026-10-24",
}


def attach_senate_institutional_context(partitions):
    """Only full calendar years; transition years are deliberately excluded."""
    indexed = {(row["year"], row["territory_code"]): row for row in partitions}
    for year in sorted(CLOSED_SENATE_YEARS):
        indexed.setdefault((year, "BR"), build_annual_partition([], year, "BR", "senado"))
    for (year, _territory), partition in indexed.items():
        if year in CLOSED_SENATE_YEARS:
            attach_suspended_year_context(partition, year)
    return [indexed[key] for key in sorted(indexed)]


def attach_suspended_year_context(partition, year):
    partition["institutional_status"] = "suspended_whole_year"
    partition["institutional_status_label"] = "Senado sem funcionamento neste ano"
    partition["institutional_status_evidence"] = SENATE_CLOSURE_EVIDENCE
    partition["institutional_status_period"] = {
        "starts_on": f"{year}-01-01", "ends_on": f"{year}-12-31",
    }
