"""Discover historical deputy identifiers without limiting history to today's roster."""

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import OFFICIAL_HOSTS, SOURCE, CrawlerConfiguration
from service.voting_pipeline.runtime import official_source_acquisition
from storage.files import save_json


def collect_historical_deputy_universe(connection, storage, legislatures):
    configuration = CrawlerConfiguration(storage.resolve())
    people, evidence = {}, []
    with official_source_acquisition(
        connection, configuration, SOURCE, OFFICIAL_HOSTS, CamaraAcquisition,
    ) as acquisition:
        for legislature in legislatures:
            for rows, artifact in acquisition.pages(
                f"deputados?idLegislatura={legislature}&itens=100&ordem=ASC&ordenarPor=id",
                "camara_historical_universe",
            ):
                evidence.append({"url": artifact.resource.url, "sha256": artifact.sha256,
                                 "fetched_at": artifact.fetched_at, "legislature": legislature})
                register_discovered_members(people, rows, legislature)
    result = {"schema_version": "camara_historical_universe.v1",
              "people": [people[key] for key in sorted(people, key=int)], "evidence": evidence,
              "semantics": "Source identifiers listed in historical legislatures; "
                           "listing alone does not prove simultaneous exercise or affiliation"}
    save_json(storage / "camara-historical-universe.json", result)
    return result


def register_discovered_members(people, rows, legislature):
    for row in rows:
        # The listing can return a deputy's latest status from another legislature.
        # Only the requested roster identifies discovery scope; exercise is verified later.
        identifier = str(row["id"])
        people.setdefault(identifier, {"id": identifier, "legislatures": []})
        if legislature not in people[identifier]["legislatures"]:
            people[identifier]["legislatures"].append(legislature)
