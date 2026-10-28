"""Qualified transcriptions of official historical signatures; never original-file hashes."""

from datetime import UTC, datetime
from hashlib import sha256

from crawlers.state_government.parsing import source_exercise
from storage.files import write_private_bytes

STATUTE_URL = "https://legis.ac.gov.br/detalhar/6565-1"
STATUTE_ROWS = (
    ("AP", "Antônio Waldez Goés da Silva", "Amapá"),
    ("AM", "Wilson Miranda de Lima", "Amazonas"),
    ("MT", "Mauro Mendes Ferreira", "Mato Grosso"),
    ("PA", "Helder Zahluth Barbalho", "Pará"),
    ("RO", "Marcos José Rocha dos Santos", "Rondônia"),
    ("TO", "Mauro Carlesse", "Tocantins"),
)
ES_2019_URL = ("https://www.es.gov.br/tags/"
               "posse-governo-esp-rito-santo-466nwrnf1v26z04cb1c4sgkrd4")
ES_2019_TEXT = (
    "Renato Casagrande é empossado como governador do Espírito Santo\n01/01/2019 19:30\n"
    "O governador eleito do Espírito Santo, Renato Casagrande, e a vice-governadora "
    "Jacqueline Moraes foram empossados oficialmente na tarde desta terça-feira (1º), "
    "na Assembleia Legislativa do Estado."
)


def reviewed_office_record(storage, *, uf, name, text, url, observed, published, kind,
                           political_party=None):
    payload = text.encode("utf-8")
    fingerprint = sha256(payload).hexdigest()
    path = storage / "reviewed-transcriptions" / (fingerprint + ".txt")
    if not path.exists():
        write_private_bytes(path, [payload])
    year = int(observed[:4])
    record = source_exercise(name, uf, f"national-observation-{year}:" + name)
    record.update(
        institution_code="district_government" if uf == "DF" else "state_government",
        original_source_name=name, date_precision="year", starts_on=None, ends_before=None,
        year_start=year, year_end=year, source_observed_on=observed, observation_kind=kind,
        source_url=url, limitation="dated_observation_not_full_year_or_continuous_affiliation",
        evidence=[{
            "url": url, "sha256": fingerprint, "sha256_scope": "reviewed_transcription",
            "original_document_sha256": None, "reviewed_transcription_path": str(path),
            "source_kind": "reviewed_official_web_transcription",
            "retrieval_channel": "official_page_search_index", "reviewed_on": "2026-10-23",
            "fetched_at": datetime.now(UTC).isoformat(), "observed_on": observed,
            "published_on": published, "locator": text,
        }],
    )
    if political_party:
        record.update(
            political_party_abbreviation=political_party,
            political_party_status="verified_official_dated_government_observation",
            political_party_context="party_reported_during_government",
            political_party_limitation="dated_observation_not_continuous_affiliation",
            political_party_year_start=year, political_party_year_end=year,
            political_party_evidence=record["evidence"],
        )
    return record


def reviewed_2019_office_records(storage):
    records = [reviewed_office_record(
        storage, uf=uf, name=name,
        text=f"São Luís/MA, 28 de novembro 2019.\n{name}\nGovernador do Estado do {state}",
        url=STATUTE_URL, observed="2019-11-28", published="2025-09-17",
        kind="historical_signature_observation",
    ) for uf, name, state in STATUTE_ROWS]
    records.append(reviewed_office_record(
        storage, uf="ES", name="Renato Casagrande", text=ES_2019_TEXT, url=ES_2019_URL,
        observed="2019-01-01", published="2019-01-01", kind="inauguration",
    ))
    return records
