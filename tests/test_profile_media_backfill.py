"""Photo recovery is tied to validated profiles, raw hashes and bounded batch writes."""

import hashlib
import json

from service.profile_media.backfill import (
    backfill_profile_photos,
    load_local_senate_photos,
    resolve_profile_photo,
)


def profile_row():
    return {
        "person_id": "internal-uuid",
        "source_code": "senado",
        "source_record_id": 1,
        "source_url": "https://legis.senado.leg.br/dadosabertos/senador/123.json",
        "profile": {
            "personId": "internal-uuid",
            "civilName": "Pessoa Exemplo",
            "birthDate": "1980-01-01",
        },
        "photo_url": None,
    }


def raw_profile():
    return {
        "IdentificacaoParlamentar": {
            "NomeCompletoParlamentar": "Pessoa Exemplo",
            "UrlFotoParlamentar": "http://www.senado.leg.br/foto.jpg",
        },
        "DadosBasicosParlamentar": {"DataNascimento": "1980-01-01"},
    }


def test_raw_name_without_birth_confirmation_cannot_recover_photo():
    row = profile_row()
    raw = raw_profile()
    raw["DadosBasicosParlamentar"]["DataNascimento"] = "1980-01-02"
    assert resolve_profile_photo(row, {row["source_url"]: raw}) is None
    assert (
        resolve_profile_photo(row, {row["source_url"]: raw_profile()})
        == "https://www.senado.leg.br/foto.jpg"
    )


def test_local_raw_must_match_immutable_hash(tmp_path):
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    archive = tmp_path / "archive.json"
    raw = json.dumps({"DetalheParlamentar": {"Parlamentar": raw_profile()}}).encode()
    archive.write_bytes(raw)
    url = profile_row()["source_url"]
    manifest = {"source_url": url, "path": str(archive), "sha256": hashlib.sha256(raw).hexdigest()}
    path = manifests / "senado-example.json"
    path.write_text(json.dumps(manifest))
    assert url in load_local_senate_photos(tmp_path, {url})
    archive.write_text("{}")
    assert load_local_senate_photos(tmp_path, {url}) == {}


class Repository:
    def __init__(self):
        self.row = {**profile_row(), "profile": {"photoUrl": "https://www.senado.leg.br/foto.jpg"}}
        self.writes = []

    def fetch_linked_profiles(self, limit):
        return [self.row]

    def save_official_photos(self, rows):
        self.writes.append(rows)
        self.row["photo_url"] = rows[0]["photo_url"]
        return len(rows)


def test_batch_replay_is_idempotent_and_dry_run_never_writes(tmp_path):
    repository = Repository()
    assert backfill_profile_photos(repository, tmp_path)["proposed_people"] == 1
    assert repository.writes == []
    assert backfill_profile_photos(repository, tmp_path, apply=True)["updated_people"] == 1
    assert backfill_profile_photos(repository, tmp_path, apply=True)["updated_people"] == 0
    assert len(repository.writes) == 1
