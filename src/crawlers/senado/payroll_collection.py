"""Finite nominal payroll collection using stored verified parliamentary profiles."""

from uuid import uuid4

import httpx

from crawlers.senado.acquisition import SenateAcquisition
from crawlers.senado.configuration import PARSER_VERSION, SOURCE, SenateConfiguration
from crawlers.senado.payroll_acquisition import previous_payroll_period
from crawlers.senado.payroll_pipeline import collect_verified_salary
from crawlers.senado.projection import SenateProjectionWriter
from database.senado_payroll import fetch_verified_payroll_profiles
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import IngestionError
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from service.observability.reporting import describe_error

ADMINISTRATIVE_HOSTS = frozenset({"adm.senado.gov.br"})


def collect_stored_profile_salaries(repository, acquisition, profiles):
    people, failures = [], []
    for profile in profiles:
        try:
            people.append({
                "person_id": profile["personId"],
                **collect_verified_salary(repository, acquisition, profile),
            })
        except Exception as error:
            failures.append({"person_id": profile["personId"], **describe_error(error)})
            if acquisition.payroll_error is not None:
                break
    return {"people": people, "failures": failures, "selected_people": len(profiles)}


def collect_senado_payroll(connection, storage, limit=100, person_id=None):
    if not 1 <= limit <= 100:
        raise IngestionError("INVALID_SENADO_PAYROLL_LIMIT")
    configuration = SenateConfiguration(storage.resolve())
    profiles = fetch_verified_payroll_profiles(
        connection, previous_payroll_period(), limit, person_id
    )
    repository = IngestionRepository(
        connection, SOURCE, SenateProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"purpose": "verified_nominal_payroll"})
    try:
        with httpx.Client(timeout=configuration.request_timeout_seconds) as client:
            acquisition = SenateAcquisition(
                configuration, OfficialHttpClient(configuration, client, ADMINISTRATIVE_HOSTS)
            )
            result = collect_stored_profile_salaries(repository, acquisition, profiles)
        result["status"] = "partial" if result["failures"] else "completed"
        repository.finish_run(result["status"], result)
        return result
    except BaseException:
        repository.finish_run("failed", {})
        raise
