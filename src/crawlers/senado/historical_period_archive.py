"""Read archived Senate API responses and verify each file against its recorded SHA-256."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from crawlers.senado.configuration import API_BASE
from crawlers.senado.historical_period_contracts import ArchivedDocument, PendingItem

NEW_SOURCE_DIRECTORY = Path("data/political-dashboard/senate-history-1992-1994-source")
EARLIER_SOURCE_DIRECTORY = Path("data/political-orientation/itamar-senate-sources")
EARLIER_KIND_SUFFIXES = {"mandates": "mandatos", "affiliations": "filiacoes"}


class SenateArchive:
    """Lookups by (kind, senator id); the newer manifest wins over the earlier acquisition."""

    def __init__(self, project_root: Path, source_directory: Path | None = None):
        self.project_root = project_root
        self.new_directory = source_directory or project_root / NEW_SOURCE_DIRECTORY
        self.earlier_directory = project_root / EARLIER_SOURCE_DIRECTORY
        self.problems: list[PendingItem] = []
        self._index = {**self._earlier_entries(), **self._new_entries()}

    def find(self, kind: str, senator_id: str | None = None) -> ArchivedDocument | None:
        entry = self._index.get((kind, senator_id))
        return self._open(entry) if entry else None

    def senator_ids_with(self, kind: str) -> set[str]:
        return {key[1] for key in self._index if key[0] == kind and key[1]}

    def _new_entries(self) -> dict:
        manifest_path = self.new_directory / "manifest.json"
        if not manifest_path.exists():
            return {}
        entries = {}
        for row in json.loads(manifest_path.read_text(encoding="utf-8")):
            if row.get("http_status") != 200 or not row.get("sha256"):
                continue
            entries[(row["kind"], row.get("senator_id"))] = {
                "kind": row["kind"],
                "senator_id": row.get("senator_id"),
                "path": self.new_directory / row["path"],
                "url": row["url"],
                "sha256": row["sha256"],
                "fetched_at": datetime.fromisoformat(row["baixado_em"]).astimezone(UTC),
                "display_path": str(Path(self.new_directory.name) / row["path"]),
            }
        return entries

    def _earlier_entries(self) -> dict:
        manifest_path = self.earlier_directory / "source-integrity-manifest.json"
        if not manifest_path.exists():
            return {}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = {}
        for row in manifest["files"]:
            name = Path(row["path"]).name
            parsed = _earlier_person_file(name)
            if parsed is None:
                continue
            kind, senator_id, service = parsed
            entries[(kind, senator_id)] = {
                "kind": kind,
                "senator_id": senator_id,
                "path": self.project_root / row["path"],
                "url": f"{API_BASE}senador/{senator_id}/{service}.json",
                "sha256": row["sha256"],
                "fetched_at": datetime.fromisoformat(manifest["reviewed_on"]).replace(tzinfo=UTC),
                "display_path": row["path"],
            }
        return entries

    def _open(self, entry: dict) -> ArchivedDocument | None:
        path: Path = entry["path"]
        kind, senator_id = entry["kind"], entry["senator_id"]
        if not path.exists():
            self._reject("ARCHIVED_RESPONSE_FILE_MISSING", senator_id, entry["display_path"])
            return None
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            self._reject("ARCHIVED_RESPONSE_HASH_MISMATCH", senator_id, entry["display_path"])
            return None
        return ArchivedDocument(
            kind=kind,
            senator_id=senator_id,
            url=entry["url"],
            sha256=entry["sha256"],
            fetched_at=entry["fetched_at"],
            archive_path=entry["display_path"],
            payload=json.loads(raw),
        )

    def _reject(self, code: str, senator_id: str | None, detail: str) -> None:
        self.problems.append(PendingItem(code, senator_id, detail, "document"))


def _earlier_person_file(name: str) -> tuple[str, str, str] | None:
    if not name.startswith("person-") or not name.endswith(".json"):
        return None
    senator_id, _, suffix = name.removeprefix("person-").removesuffix(".json").partition("-")
    for kind, service in EARLIER_KIND_SUFFIXES.items():
        if suffix == service and senator_id.isdigit():
            return kind, senator_id, service
    return None
