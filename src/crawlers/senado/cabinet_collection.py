"""Bounded monthly staff payroll acquisition, with exact verified cabinet attribution."""

import re
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx

from crawlers.senado.cabinet_payroll import aggregate_staff_payroll, cabinet_month_record
from crawlers.senado.cabinet_staging import (
    PARSER_VERSION,
    CabinetPayrollProjectionWriter,
    stage_cabinet_payroll,
)
from crawlers.senado.configuration import SOURCE, SenateConfiguration
from crawlers.senado.normalization import current_members
from database.cabinet_payroll import fetch_verified_senate_people
from normalization.identity import normalize_person_name
from parsing.html import HtmlLinksParser
from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient, validate_official_url
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter

INDEX_URL = "https://www.senado.leg.br/transparencia/rh/servidores/consulta_remuneracao.asp"
HOSTS = frozenset({"www.senado.leg.br", "legis.senado.leg.br"})
MONTH_PATH = re.compile(
    r"/transparencia/LAI/secrh/SF_ConsultaRemuneracaoServidoresParlamentares_(20\d{2})(\d{2})\.csv"
)


def discover_staff_months(payload, months=None, maximum=12):
    if not 1 <= maximum <= 12:
        raise IngestionError("INVALID_CABINET_PAYROLL_LIMIT")
    parser = HtmlLinksParser()
    parser.feed(payload.decode("latin1"))
    published = {}
    for link in parser.links:
        url = urljoin(INDEX_URL, link)
        match = MONTH_PATH.fullmatch(urlsplit(url).path)
        if match and 1 <= int(match[2]) <= 12:
            validate_official_url(url, HOSTS)
            published[f"{match[1]}-{match[2]}"] = url
    if not published:
        raise IngestionError("SENADO_CABINET_PAYROLL_INDEX_EMPTY")
    requested = set(months or [])
    if requested - published.keys():
        raise IngestionError("SENADO_PAYROLL_MONTH_NOT_PUBLISHED")
    selected = requested or published.keys()
    return [(period, published[period]) for period in sorted(selected, reverse=True)[:maximum]]


def verified_cabinet_index(members, people):
    people_by_name = defaultdict(dict)
    for person in people:
        people_by_name[normalize_person_name(person["civil_name"])][person["person_id"]] = person
    cabinets = defaultdict(dict)
    for member in members:
        identity = member["IdentificacaoParlamentar"]
        matches = people_by_name[normalize_person_name(identity["NomeCompletoParlamentar"])]
        if len(matches) == 1:
            cabinets[normalize_person_name(identity["NomeParlamentar"])].update(matches)
    return {name: next(iter(ids.values())) for name, ids in cabinets.items() if len(ids) == 1}


def acquire_document(configuration, transport, budget, url, kind, suffix):
    from storage.files import hash_content

    resource = Resource(
        "senado-" + hash_content(url),
        kind,
        url,
        kind,
        datetime.now(UTC).year,
        "senado-cabinet-payroll",
        file_suffix=suffix,
    )
    return download_resource(resource, configuration, transport, budget)


def collect_staff_month(repository, configuration, transport, budget, period, url, index):
    artifact = acquire_document(
        configuration, transport, budget, url, "senado_cabinet_payroll", ".csv"
    )
    cabinets, skipped = aggregate_staff_payroll(artifact.path.read_bytes(), period)
    records = [
        cabinet_month_record(index[name]["person_id"], period, roles, artifact)
        for name, roles in sorted(cabinets.items())
        if name in index
    ]
    if not records:
        raise IngestionError("SENADO_CABINET_IDENTITY_NOT_CONFIRMED")
    profiles_by_id = {person["person_id"]: person for person in index.values()}
    for record in records:
        record["identityEvidence"] = {
            "method": "verified_senado_profile_and_official_roster_name",
            "profileSourceRecordId": profiles_by_id[record["personId"]]["source_record_id"],
            "roster": profiles_by_id[record["personId"]].get("roster_evidence"),
        }
    staged = stage_cabinet_payroll(artifact, configuration, records)
    result = asdict(repository.ingest_validated_artifact(staged, configuration.batch_size))
    return {
        "period": period,
        "matched_cabinets": len(records),
        "unmatched_cabinets": len(cabinets) - len(records),
        "excluded_rows": skipped,
        **result,
    }


def collect_cabinet_payroll(connection, storage, months=None, maximum=12):
    import json

    configuration = SenateConfiguration(storage.resolve())
    budget = DownloadBudget()
    repository = IngestionRepository(
        connection,
        SOURCE,
        CabinetPayrollProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "cabinet_staff_payroll"})
    results = []
    try:
        with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
            transport = OfficialHttpClient(configuration, client, HOSTS)
            catalog = acquire_document(
                configuration, transport, budget, INDEX_URL, "senado_staff_payroll_index", ".html"
            )
            selected = discover_staff_months(catalog.path.read_bytes(), months, maximum)
            roster = acquire_document(
                configuration,
                transport,
                budget,
                "https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json",
                "senado_roster",
                ".json",
            )
            index = verified_cabinet_index(
                current_members(json.loads(roster.path.read_bytes())),
                fetch_verified_senate_people(connection),
            )
            for person in index.values():
                person["roster_evidence"] = {
                    "url": roster.resource.url,
                    "sha256": roster.sha256,
                    "fetched_at": roster.fetched_at,
                }
            for period, url in selected:
                results.append(
                    collect_staff_month(
                        repository, configuration, transport, budget, period, url, index
                    )
                )
        status = (
            "partial"
            if any(r["unmatched_cabinets"] or r["rejected"] for r in results)
            else "completed"
        )
        result = {"status": status, "months": results, "verified_cabinets": len(index)}
        repository.finish_run(status, result)
        return result
    except BaseException:
        repository.finish_run("failed", {"months": results})
        raise
