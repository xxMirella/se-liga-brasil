"""Dated first-party statements; these are not government membership certificates."""

PARTY_2026_OBSERVATIONS = (
    ("RS", "Eduardo Leite", "PSD", "2026-03-23", "2026-03-23", "office_observation",
     "https://psd.org.br/noticias/mateus-simoes-psd-assume-o-governo-de-minas-gerais/",
     ("23 de mar de 2026", "são filiados ao partido os governadores do Rio Grande do Sul "
      "(Eduardo Leite)")),
    ("MS", "Eduardo Riedel", "PP", "2026-08-01", "2026-08-01", "office_observation",
     "https://progressistas.org.br/noticias-progressistas/riedel-reune-nove-partidos-e-lanca-"
     "reeleicao-com-frente-unificada-pelo-desenvolvimento-de-ms/",
     ("01/08/2026", "O governador Eduardo Riedel (PP)")),
    ("AM", "Roberto Cidade", "UNIÃO", "2026-07-16", "2026-07-16", "office_observation",
     "https://uniaobrasil.org.br/adjuto-afonso-uniao-e-eleito-presidente-da-assembleia-legislativa-do-amazonas/",
     ("16/07/2026", "Roberto Cidade (União) para assumir o governo do Amazonas",
      "O governador Roberto Cidade")),
)
PARTY_STATEMENT_URLS = frozenset(row[6] for row in PARTY_2026_OBSERVATIONS)


def qualify_party_statement(record):
    """Keep the source organization and limited temporal scope visible to readers."""
    record.update(
        political_party_status="verified_party_official_dated_government_statement",
        political_party_context="political_party_self_reported_government",
        political_party_limitation=(
            "party_self_reported_dated_statement_not_government_membership_certificate"
        ),
    )
    for proof in record["evidence"]:
        proof["source_kind"] = "political_party_official_reporting"
    return record
