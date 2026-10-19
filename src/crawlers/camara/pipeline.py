"""Collect a personally verified federal deputy's missing institutional facts."""

from dataclasses import asdict
from datetime import date
from urllib.parse import urlencode

from crawlers.camara.configuration import API_BASE, PORTAL_BASE
from crawlers.camara.normalization import normalize_profile, normalize_proposition
from crawlers.camara.payroll import normalize_salary, published_salary_months
from crawlers.camara.staging import stage_records
from database.enrichment import match_official_person
from service.ingestion.contracts import DownloadedArtifact
from storage.files import hash_content, hash_file, save_json


def bundle_profile_artifacts(acquisition, artifacts):
    references = [
        {"url": a.resource.url, "sha256": a.sha256, "path": str(a.path)} for a in artifacts
    ]
    path = (
        acquisition.configuration.storage_directory
        / "bundles"
        / (hash_content(references) + ".json")
    )
    if not path.exists():
        save_json(path, references)
    artifact = artifacts[0]
    return DownloadedArtifact(
        artifact.resource,
        path,
        hash_file(path),
        max(a.fetched_at for a in artifacts),
        path.stat().st_size,
    )


def collect_person_profile(acquisition, connection, candidate, member):
    subject_id = member["id"]
    document, profile_artifact = acquisition.json_document(
        f"deputados/{subject_id}", "camara_profile"
    )
    profile = document["dados"]
    method = match_official_person(connection, profile, candidate["person_id"])
    history, history_artifact = acquisition.json_document(
        f"deputados/{subject_id}/historico", "camara_history"
    )
    legislature_id = profile["ultimoStatus"]["idLegislatura"]
    legislature, term_artifact = acquisition.json_document(
        f"legislaturas/{legislature_id}", "camara_legislature"
    )
    data = normalize_profile(
        profile, history["dados"], legislature["dados"], candidate["person_id"], method
    )
    artifacts = [profile_artifact, history_artifact, term_artifact]
    data["evidence"] = [{"url": a.resource.url, "sha256": a.sha256} for a in artifacts]
    return data, bundle_profile_artifacts(acquisition, artifacts)


def ingest_collected(repository, acquisition, artifact, rows) -> dict:
    validated = stage_records(artifact, acquisition.configuration, rows)
    return asdict(
        repository.ingest_validated_artifact(validated, acquisition.configuration.batch_size)
    )


def collect_current_salary(acquisition, repository, member, profile) -> dict:
    year = str(date.today().year)
    base = PORTAL_BASE + str(member["id"])
    index = acquisition.acquire(base + "/remuneracao?ano=" + year, "camara_salary_index", ".html")
    months = published_salary_months(index.path.read_bytes())
    if not months:
        return {"status": "not_published", "source_url": index.resource.url}
    month = months[-1]
    url = base + "/remuneracao-deputado-detalhado?mesAno=" + month[5:7] + month[:4]
    artifact = acquisition.acquire(url, "camara_payroll", ".html")
    salary = normalize_salary(artifact.path.read_bytes(), month, profile)
    return {
        "competence": salary["competence"],
        **ingest_collected(repository, acquisition, artifact, [salary]),
    }


def collect_authored_propositions(acquisition, repository, member, person_id) -> dict:
    query = urlencode(
        {"idDeputadoAutor": member["id"], "itens": 100, "ordem": "ASC", "ordenarPor": "id"}
    )
    count, pages = 0, 0
    for rows, artifact in acquisition.pages(
        API_BASE + "proposicoes?" + query, "camara_propositions"
    ):
        normalized = [normalize_proposition(row, person_id) for row in rows]
        ingest_collected(repository, acquisition, artifact, normalized)
        count += len(normalized)
        pages += 1
    from database.legislative_collection import select_proposition_keys
    from service.legislative_collection.sources import camara_pipeline

    keys = select_proposition_keys(repository.connection, "camara", [person_id], limit=25)
    history = camara_pipeline(
        "history", acquisition.configuration, acquisition, repository, keys=keys, maximum=25
    )
    return {"records": count, "pages": pages, "history": history,
            "coverage": "authorship_only_approval_not_inferred"}


def enrich_person(acquisition, repository, candidate, member) -> dict:
    profile, artifact = collect_person_profile(
        acquisition, repository.connection, candidate, member
    )
    result = {"person_id": candidate["person_id"]}
    result["profile"] = ingest_collected(repository, acquisition, artifact, [profile])
    requested = set(candidate.get("requested_fields") or {"current_salary", "political_activity"})
    if "current_salary" in requested:
        result["salary"] = collect_current_salary(acquisition, repository, member, profile)
    if "political_activity" in requested:
        result["propositions"] = collect_authored_propositions(
            acquisition, repository, member, candidate["person_id"]
        )
    from crawlers.camara.attendance import collect_attendance_history

    if "attendance" in requested:
        result["attendance"] = collect_attendance_history(
            acquisition, repository, member, candidate["person_id"],
        )
    return result
