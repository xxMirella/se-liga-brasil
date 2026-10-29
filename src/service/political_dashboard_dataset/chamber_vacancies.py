"""Reviewed vacancy at the 2020 closing snapshot, bounded by two official transitions."""


def chamber_2020_vacancy(histories, manifests):
    indexed = {row["official_deputy_id"]: row for row in histories}
    departure = indexed["178874"]["events"]
    successor = indexed["74165"]["events"]
    resigned = any(row["idLegislatura"] == 56 and row["dataHora"] == "2020-12-31T00:00"
                   and row["situacao"] == "VACANCIA" and row["siglaUf"] == "ES"
                   and row["descricaoStatus"].endswith("Renúncia") for row in departure)
    assumed = any(row["idLegislatura"] == 56 and row["dataHora"] == "2021-01-01T17:36"
                  and row["situacao"] == "Exercício" and row["siglaUf"] == "ES"
                  and row["descricaoStatus"].startswith("Entrada - Posse de Suplente")
                  for row in successor)
    if not resigned or not assumed:
        raise ValueError("CHAMBER_2020_REVIEWED_VACANCY_NO_LONGER_CORROBORATED")
    return {"uf": "ES", "vacant_on": "2020-12-31", "departed_source_person_id": "178874",
            "successor_source_person_id": "74165", "successor_assumed_at": "2021-01-01T17:36",
            "evidence_manifest_sha256": [manifests["178874"], manifests["74165"]],
            "source_urls": [f"https://dadosabertos.camara.leg.br/api/v2/deputados/{identifier}"
                            "/historico" for identifier in ("178874", "74165")]}
