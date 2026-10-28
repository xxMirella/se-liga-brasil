"""Historical legislature rolls remain separate from verified annual seat snapshots."""

from collections import defaultdict

from crawlers.senado.historical_parsing import parse_legislature_roster
from service.political_dashboard_dataset.aggregation import build_annual_partition


def collect_legislature_rosters(acquisition, legislatures, progress):
    rows = []
    for legislature in legislatures:
        payload, evidence = acquisition.acquire(
            f"senador/lista/legislatura/{legislature}.json"
        )
        rows.extend(parse_legislature_roster(payload, legislature, evidence))
        progress({"stage": "historical_rosters", "legislature": legislature,
                  "roster_records": len(rows)})
    return rows


def attach_historical_rosters(partitions, rosters, first_year, last_year):
    indexed = {(row["year"], row["territory_code"]): row for row in partitions}
    grouped = defaultdict(list)
    for row in rosters:
        start = max(first_year, int(row["period_start"][:4]))
        end = min(last_year, int(row["period_end"][:4]))
        for year in range(start, end + 1):
            for territory in {"BR", row["uf"]}:
                grouped[year, territory].append(row)
    for (year, territory), rows in grouped.items():
        partition = indexed.setdefault(
            (year, territory), build_annual_partition([], year, territory, "senado")
        )
        previous_count = len(partition.get("historical_roster", []))
        partition["historical_roster"] = rows
        partition["source_observation_count"] += len(rows) - previous_count
        if partition["coverage"] == "not_available":
            partition["coverage"] = "legislature_roster_only"
    return [indexed[key] for key in sorted(indexed)]
