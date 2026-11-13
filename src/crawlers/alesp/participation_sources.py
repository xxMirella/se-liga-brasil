"""Bounded official acquisition, immutable snapshots and a resumable document queue."""

import json
from collections import deque
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path

from crawlers.alesp.configuration import OFFICIAL_HOSTS
from service.acquisition.http_client import validate_official_url
from storage.files import hash_file, load_json, save_json

API = "https://legis-api-portal-prd.al.sp.gov.br"
COMMISSION_URL = (
    "https://www3.al.sp.gov.br/repositorio/dados-abertos/output/json/presenca-comissoes.json"
)
PARTICIPATION_HOSTS = OFFICIAL_HOSTS | {"www3.al.sp.gov.br"}
DISCOVERY_KINDS = {"meeting_index", "session_index", "session_integral", "meeting_participants"}


def cached_participation_sources(storage_directory):
    manifest = storage_directory / "participation/manifest.json"
    for reference in load_json(manifest, []):
        validate_official_url(reference["url"], PARTICIPATION_HOSTS)
        if hash_file(Path(reference["path"])) != reference["sha256"]:
            raise ValueError("ALESP_PARTICIPATION_CHECKSUM_MISMATCH")
        yield reference


def download_participation_source(directory, transport, task, max_bytes=32 * 1024**2):
    validate_official_url(task["url"], PARTICIPATION_HOSTS)
    content = transport.fetch_bytes(task["url"], max_bytes=max_bytes)
    digest = sha256(content).hexdigest()
    path = directory / (digest + ".source")
    path.write_bytes(content)
    path.chmod(0o600)
    return task | {
        "path": str(path.resolve()),
        "sha256": hash_file(path),
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def meeting_document_tasks(payload):
    for meeting in payload.get("content", []):
        if (meeting.get("status") or {}).get("txNome") not in {"Realizada", "Sem Quórum"}:
            continue
        for document in meeting.get("documentosReuniao") or []:
            kind = {37: "minutes", 20017: "transcript"}.get(document.get("idTipoDocumento"))
            url = document.get("linkArquivo") or document.get("linkArquivoPDF")
            if kind and url:
                yield {
                    "kind": kind,
                    "url": url,
                    "event_date": meeting["dtReuniao"][:10],
                    "event_occurred": True,
                    "event_key": "committee:" + str(meeting["idReuniao"]),
                    "event_type": meeting.get("tituloReuniao"),
                }


def session_integral_tasks(payload):
    for session in payload.get("content", []):
        if session.get("temIntegra") and session.get("situacao") in {
            "Realizada",
            "Encerrada",
            "Levantada",
            "Publicada (Íntegra)",
        }:
            yield {
                "kind": "session_integral",
                "url": API + f"/sessoes-plenarias/{session['id']}/integra",
                "event_date": session["dtInicio"][:10],
                "event_occurred": True,
                "event_key": "plenary:" + str(session["id"]),
                "event_type": session["tipo"],
            }


def discovered_tasks(reference):
    payload = json.loads(Path(reference["path"]).read_bytes())
    if reference["kind"] == "meeting_index":
        return [
            {
                "kind": "meeting_participants",
                "url": API + f"/colegiado/reuniao/{meeting['idReuniao']}",
                "event_type": meeting.get("tituloReuniao"),
            }
            for meeting in payload.get("content", [])
            if (meeting.get("status") or {}).get("txNome") in {"Realizada", "Sem Quórum"}
        ]
    if reference["kind"] == "meeting_participants":
        return list(meeting_document_tasks({"content": [payload]}))
    if reference["kind"] == "session_index":
        return list(session_integral_tasks(payload))
    if reference["kind"] == "session_integral" and payload.get("urlIntegra"):
        return [reference_task(reference) | {"kind": "transcript", "url": payload["urlIntegra"]}]
    return []


def reference_task(reference):
    return {
        key: value
        for key, value in reference.items()
        if key not in {"path", "sha256", "fetched_at"}
    }


def initial_participation_tasks(registrations, cursor):
    tasks = [{"kind": "commission_export", "url": COMMISSION_URL}]
    for kind, route in [
        ("meeting_index", "/colegiado/reunioes"),
        ("session_index", "/sessoes-plenarias/consulta"),
    ]:
        page_size = 50 if kind == "session_index" else 10
        tasks.append({"kind": kind, "url": API + f"{route}?page={cursor}&size={page_size}"})
    today = date.today()
    for registration in sorted(registrations):
        for offset in range(1, 13):
            month_index = today.year * 12 + today.month - 1 - offset
            year, month = divmod(month_index, 12)
            tasks.append(
                {
                    "kind": "plenary_register",
                    "registration": registration,
                    "url": API + f"/lista-presenca-parlamentar/{registration}/{month + 1}/{year}",
                }
            )
    return tasks


def acquire_participation_sources(storage_directory, transport, registrations, max_requests=40):
    directory = storage_directory / "participation"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = load_json(directory / "manifest.json", [])
    state = load_json(directory / "queue.json", {"cursor": 0, "pending": []})
    cached_by_url = {entry["url"]: entry for entry in manifest}
    pending, cursor = prepare_participation_queue(state, registrations)
    remaining_bytes = getattr(
        getattr(transport, "configuration", None), "max_run_download_bytes", 100 * 1024**2
    )
    retry_tasks = []
    failures, requests = [], 0
    while pending and requests < max_requests and remaining_bytes > 0:
        task = pending.popleft()
        if task["url"] in cached_by_url:
            cached = cached_by_url[task["url"]]
            if cached["kind"] in DISCOVERY_KINDS:
                pending.extendleft(reversed(discovered_tasks(cached)))
            continue
        requests += 1
        try:
            reference = download_participation_source(
                directory, transport, task, min(32 * 1024**2, remaining_bytes)
            )
            remaining_bytes -= Path(reference["path"]).stat().st_size
            children = discovered_tasks(reference) if task["kind"] in DISCOVERY_KINDS else []
            manifest.append(reference)
            cached_by_url[task["url"]] = reference
            pending.extendleft(reversed(children))
            save_json(directory / "manifest.json", manifest)
            save_json(
                directory / "queue.json",
                {
                    "cursor": cursor,
                    "pending": list(pending) + retry_tasks,
                },
            )
        except Exception as error:
            failures.append({"url": task["url"], "error": type(error).__name__})
            retry_tasks.append(task)
    pending.extend(retry_tasks)
    save_json(directory / "queue.json", {"cursor": cursor, "pending": list(pending)})
    return {"remote_requests": requests, "pending_resources": len(pending), "failures": failures}


def prepare_participation_queue(state, registrations):
    cursor = state["cursor"]
    pending = list(state["pending"])
    if not pending:
        return deque(initial_participation_tasks(registrations, cursor)), cursor + 1
    if all(task["kind"] == "plenary_register" for task in pending):
        pending[0:0] = initial_participation_tasks({}, cursor)
        cursor += 1
    return deque(pending), cursor
