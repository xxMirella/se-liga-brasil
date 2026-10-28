"""Explicitly qualified, manually reviewed official text when HTTP serves other content.

The fingerprint covers this transcription, NEVER the unavailable original document.
Official web retrieval reviewed on 2026-10-23, published 2023-04-12 15h04.
"""

from datetime import UTC, datetime
from hashlib import sha256

from crawlers.state_government.parsing import source_exercise
from storage.files import write_private_bytes

ES_URL = ("https://www.es.gov.br/Noticia/"
          "governador-recebe-nova-diretoria-de-entidade-dos-prefeitos-capixabas")
ES_TEXT = (
    "Publicado em: 12/04/2023 15h04\n"
    "O governador do Estado, Renato Casagrande, participou, na manhã desta quarta-feira (12), "
    "da cerimônia de posse da nova diretoria da Associação dos Municípios do Estado do "
    "Espírito Santo (Amunes)."
)


def es_reviewed_observation(storage):
    payload = ES_TEXT.encode("utf-8")
    fingerprint = sha256(payload).hexdigest()
    path = storage / "reviewed-transcriptions" / (fingerprint + ".txt")
    if not path.exists():
        write_private_bytes(path, [payload])
    record = source_exercise(
        "Renato Casagrande", "ES", "national-observation-2023:Renato Casagrande",
    )
    record.update(
        date_precision="year", starts_on=None, ends_before=None, year_start=2023, year_end=2023,
        source_observed_on="2023-04-12", observation_kind="office_observation", source_url=ES_URL,
        limitation="dated_observation_not_full_year_or_continuous_affiliation",
        evidence=[{
            "url": ES_URL, "sha256": fingerprint, "sha256_scope": "reviewed_transcription",
            "original_document_sha256": None, "reviewed_transcription_path": str(path),
            "source_kind": "reviewed_official_web_transcription",
            "retrieval_channel": "official_page_via_web_tool", "reviewed_on": "2026-10-23",
            "fetched_at": datetime.now(UTC).isoformat(), "observed_on": "2023-04-12",
            "published_on": "2023-04-12", "locator": ES_TEXT,
        }],
    )
    return record
