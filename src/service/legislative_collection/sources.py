"""Thin adapters reuse source collectors and the shared execution lifecycle."""

from functools import partial

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import OFFICIAL_HOSTS as CAMARA_HOSTS
from crawlers.camara.configuration import PARSER_VERSION as CAMARA_PARSER
from crawlers.camara.configuration import SOURCE as CAMARA_SOURCE
from crawlers.camara.configuration import CrawlerConfiguration as CamaraConfiguration
from crawlers.camara.legislative_history import collect_legislative_history
from crawlers.camara.projection import CamaraProjectionWriter
from crawlers.cmsp.acquisition import MunicipalAcquisition
from crawlers.cmsp.configuration import OFFICIAL_HOSTS as CMSP_HOSTS
from crawlers.cmsp.configuration import PARSER_VERSION as CMSP_PARSER
from crawlers.cmsp.configuration import SOURCE as CMSP_SOURCE
from crawlers.cmsp.configuration import CrawlerConfiguration as MunicipalConfiguration
from crawlers.cmsp.pipeline import collect_municipal_legislation
from crawlers.cmsp.projection import MunicipalProjectionWriter
from database.legislative_collection import select_proposition_keys
from service.legislative_collection.runtime import CollectionDefinition, run_official_collection


def camara_pipeline(command, configuration, acquisition, repository, *, keys, maximum):
    from crawlers.camara.author_identity import prepare_author_resolver

    resolver, identity = prepare_author_resolver(acquisition, repository.connection, keys)
    results = collect_legislative_history(
        acquisition, repository, keys, resolve_person=resolver, max_propositions=maximum
    )
    return {
        "artifacts": [],
        "documents": results,
        "failures": [],
        "coverage": "known_documents_only",
        **identity,
    }


def collect_camara_history(
    connection, storage, person_ids=None, *, limit=25, start=None, end=None, proposition_ids=(),
):
    if any(not str(key).isdecimal() for key in proposition_ids) or len(proposition_ids) > 100:
        raise ValueError("Invalid bounded proposition identifiers")
    keys = [
        f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{key}" for key in proposition_ids
    ] or select_proposition_keys(
        connection, "camara", person_ids, limit=limit, start=start, end=end
    )
    configuration = CamaraConfiguration(storage.resolve())
    definition = CollectionDefinition(
        CAMARA_SOURCE,
        CAMARA_PARSER,
        CAMARA_HOSTS,
        CamaraProjectionWriter,
        CamaraAcquisition,
    )
    pipeline = partial(camara_pipeline, keys=keys, maximum=limit)
    return run_official_collection(connection, configuration, definition, pipeline)


def municipal_pipeline(command, configuration, acquisition, repository, *, years, bindings):
    results = []
    for entry in collect_municipal_legislation(
        acquisition,
        years,
        reviewed_bindings=bindings,
        repository=repository,
    ):
        results.append(
            entry["ingestion"]
            | {
                "year": entry["year"],
                "domain": entry["domain"],
                "artifact_sha256": entry["artifactSha256"],
                "coverage": entry["coverage"],
            }
        )
    return {
        "artifacts": results,
        "failures": [],
        "identity_unresolved": bool(results),
        "coverage": "reviewed_author_bindings_only_not_entire_career",
    }


def collect_cmsp_history(connection, storage, years, *, reviewed_bindings=()):
    years = tuple(sorted(set(years)))
    if not years or len(years) > 2:
        raise ValueError("Select one or two municipal annual partitions per run")
    definition = CollectionDefinition(
        CMSP_SOURCE,
        CMSP_PARSER,
        CMSP_HOSTS,
        MunicipalProjectionWriter,
        MunicipalAcquisition,
    )
    pipeline = partial(municipal_pipeline, years=years, bindings=reviewed_bindings)
    return run_official_collection(
        connection, MunicipalConfiguration(storage.resolve()), definition, pipeline
    )
