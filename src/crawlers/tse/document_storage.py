"""Store PDFs as opaque evidence; no OCR or legal interpretation."""

import hashlib
import re
from pathlib import PurePosixPath
from uuid import uuid4

from crawlers.tse.configuration import CrawlerConfiguration
from service.ingestion.contracts import DownloadedArtifact, IngestionError
from storage.files import CHUNK_BYTES, create_private_directory, hash_content


def parse_document_identity(entry_name: str, artifact: DownloadedArtifact) -> dict:
    filename = PurePosixPath(entry_name).name
    match = re.fullmatch(r"(\d{4})([A-Z]{2})(\d+)_.+\.pdf(?:\.pdf)?", filename, re.IGNORECASE)
    if not match or int(match[1]) != artifact.resource.year:
        raise IngestionError("UNRECOGNIZED_DOCUMENT_ID")
    if artifact.resource.uf and match[2] != artifact.resource.uf:
        raise IngestionError("DOCUMENT_UF_MISMATCH")
    return {
        "electionYear": int(match[1]),
        "representedUf": match[2],
        "candidateSequence": match[3],
        "documentKind": artifact.resource.kind,
        "originalEntryName": entry_name,
    }


def save_pdf_evidence(source, configuration: CrawlerConfiguration) -> dict:
    directory = configuration.storage_directory / "documents"
    create_private_directory(directory)
    temporary = directory / f"{uuid4().hex}.part"
    digest = hashlib.sha256()
    byte_count = 0
    try:
        with temporary.open("xb") as output:
            temporary.chmod(0o600)
            signature = source.read(5)
            if signature != b"%PDF-":
                raise IngestionError("INVALID_PDF_SIGNATURE")
            output.write(signature)
            digest.update(signature)
            byte_count = len(signature)
            for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
                byte_count += len(chunk)
                if byte_count > configuration.max_entry_bytes:
                    raise IngestionError("DOCUMENT_TOO_LARGE")
                digest.update(chunk)
                output.write(chunk)
        sha256 = digest.hexdigest()
        path = directory / f"{sha256}.pdf"
        temporary.replace(path)
        return {"storageReference": str(path), "documentSha256": sha256, "bytes": byte_count}
    finally:
        temporary.unlink(missing_ok=True)


def stage_document(
    source, entry_name: str, artifact: DownloadedArtifact, configuration: CrawlerConfiguration
) -> dict:
    data = parse_document_identity(entry_name, artifact) | save_pdf_evidence(source, configuration)
    hash_data = {key: value for key, value in data.items() if key != "storageReference"}
    return {
        "kind": artifact.resource.kind,
        "externalKey": f"{artifact.resource.year}:{entry_name}",
        "normalizedData": data,
        "contentSha256": hash_content(hash_data),
        "sourceGeneratedAt": artifact.fetched_at,
        "entryName": entry_name,
        "rowNumber": None,
    }
