"""Offline-job territorial inventory; current IBGE identifiers do not prove past existence."""

import json
from dataclasses import dataclass
from pathlib import Path

from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content, save_json

BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"
OFFICIAL_HOSTS = frozenset({"servicodados.ibge.gov.br"})
SPECIAL_DISTRICT_CODES = frozenset({"5300108", "2605459"})


@dataclass(frozen=True)
class TerritoryConfiguration:
    storage_directory: Path
    max_download_bytes: int = 16 * 1024**2
    max_run_download_bytes: int = 32 * 1024**2
    request_timeout_seconds: int = 60
    max_attempts: int = 2
    force_recheck_after_hours: int = 168
    request_min_interval_seconds: float = 1.5


def acquire_catalog(configuration, client, endpoint, budget):
    url = BASE_URL + "/" + endpoint
    resource = Resource("ibge-" + hash_content(url), endpoint, url, "territorial_catalog",
                        0, "ibge-territories", "BR", ".json")
    transport = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
    artifact = download_resource(resource, configuration, transport, budget)
    return json.loads(artifact.path.read_bytes()), artifact


def normalize_current_states(payload):
    states = [{"ibge_code": str(row["id"]), "uf": row["sigla"], "name": row["nome"]}
              for row in payload]
    if len(states) != 27 or len({row["uf"] for row in states}) != 27:
        raise IngestionError("IBGE_CURRENT_STATE_CATALOG_INCOMPLETE")
    return sorted(states, key=lambda row: row["uf"])


def municipality_state(row):
    immediate = row.get("regiao-imediata") or {}
    intermediate = immediate.get("regiao-intermediaria") or {}
    if intermediate.get("UF"):
        return intermediate["UF"]["sigla"]
    microregion = row.get("microrregiao") or {}
    mesoregion = microregion.get("mesorregiao") or {}
    if mesoregion.get("UF"):
        return mesoregion["UF"]["sigla"]
    raise IngestionError("IBGE_MUNICIPALITY_STATE_MISSING")


def normalize_current_municipalities(payload, states):
    state_codes = {row["uf"] for row in states}
    municipalities, special_districts, seen = [], [], set()
    for row in payload:
        code, uf = str(row["id"]), municipality_state(row)
        if len(code) != 7 or not code.isascii() or not code.isdigit() or code in seen:
            raise IngestionError("IBGE_MUNICIPALITY_INVALID_IDENTIFIER")
        if uf not in state_codes:
            raise IngestionError("IBGE_MUNICIPALITY_STATE_UNKNOWN")
        seen.add(code)
        normalized = {"ibge_code": code, "name": row["nome"], "uf": uf}
        target = special_districts if uf == "DF" or code in SPECIAL_DISTRICT_CODES else municipalities
        target.append(normalized)
    return sorted(municipalities, key=lambda row: (row["uf"], row["name"])), special_districts


def collect_current_territories(configuration, client):
    budget = DownloadBudget()
    state_payload, state_artifact = acquire_catalog(configuration, client, "estados", budget)
    municipality_payload, municipal_artifact = acquire_catalog(
        configuration, client, "municipios", budget,
    )
    states = normalize_current_states(state_payload)
    municipalities, special_districts = normalize_current_municipalities(
        municipality_payload, states,
    )
    payload = {
        "schema_version": "ibge_current_territories.v1", "states": states,
        "municipalities": municipalities, "special_districts": special_districts,
        "temporal_scope": "current_catalog_only_not_historical_existence",
        "observed_at": municipal_artifact.fetched_at,
        "evidence": [{"url": item.resource.url, "sha256": item.sha256,
                      "fetched_at": item.fetched_at} for item in
                     (state_artifact, municipal_artifact)],
    }
    save_json(configuration.storage_directory / "territories.json", payload)
    return payload
