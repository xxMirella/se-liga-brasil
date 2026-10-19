"""Private document fingerprints; raw CPF never enters normalized payloads or logs."""

import hashlib
import hmac
import os
from pathlib import Path

from normalization.identity import normalize_cpf, normalize_person_name
from service.ingestion.contracts import IngestionError
from storage.files import create_private_directory


def load_identity_key() -> bytes:
    configured = os.getenv("SE_LIGA_BRASIL_IDENTITY_KEY")
    if configured:
        if len(configured.encode()) < 32:
            raise IngestionError("IDENTITY_KEY_TOO_SHORT")
        return configured.encode()
    project_root = Path(__file__).resolve().parents[3]
    path = project_root / "data/private/identity.key"
    create_private_directory(path.parent)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(os.urandom(32))
    except FileExistsError:
        pass
    key = path.read_bytes()
    if len(key) < 32:
        raise IngestionError("IDENTITY_KEY_TOO_SHORT")
    return key


class IdentityEvidenceBuilder:
    def __init__(self, key: bytes) -> None:
        self.key = key

    def build_evidence(self, full_name: str, cpf=None) -> dict:
        try:
            cpf = normalize_cpf(cpf)
            status = "validated" if cpf else "missing"
        except IngestionError:
            cpf, status = None, "invalid"
        fingerprint = (
            hmac.new(self.key, f"cpf:{cpf}".encode(), hashlib.sha256).hexdigest() if cpf else None
        )
        return {
            "documentKind": "cpf",
            "documentFingerprint": fingerprint,
            "documentStatus": status,
            "normalizedName": normalize_person_name(full_name),
        }
