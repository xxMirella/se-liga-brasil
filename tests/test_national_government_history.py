"""Guard dated inauguration observations against false annual continuity."""

from pathlib import Path

import pytest

from crawlers.state_government.national_observations import newspaper_text, require_locators
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.national_government_history.collection import annual_observation, observation_coverage
from service.national_government_history.reviewed_legal_observations import (
    reviewed_2019_office_records,
)
from service.national_government_history.reviewed_transcriptions import es_reviewed_observation


def artifact():
    resource = Resource("fixture", "fixture", "https://official.example/fixture", "fixture", 2023,
                        "isolated-fixture")
    return DownloadedArtifact(resource, Path("isolated-fixture"), "a" * 64,
                              "2026-10-23T00:00:00Z", 10)


def test_inauguration_party_is_observation_and_never_continuous_mandate():
    record = annual_observation(
        artifact(), "Pessoa (PSDB) tomou posse", uf="RS", name="Pessoa", party="PSDB",
        locators=("Pessoa (PSDB) tomou posse",),
    )
    assert record["year_start"] == record["year_end"] == 2023
    assert record["starts_on"] is None and record["ends_before"] is None
    assert record["source_observed_on"] == "2023-01-01"
    assert record["political_party_limitation"] == "dated_observation_not_continuous_affiliation"
    assert record["canonical_person_id"] is None


def test_no_party_is_unknown_and_df_is_not_a_state_or_municipality():
    record = annual_observation(
        artifact(), "Pessoa tomou posse", uf="DF", name="Pessoa", party=None,
        locators=("Pessoa tomou posse",),
    )
    assert record["institution_code"] == "district_government"
    assert record["political_party_status"] == "unknown"
    assert "political_party_abbreviation" not in record


def test_changed_name_party_or_posse_wording_is_rejected():
    with pytest.raises(IngestionError):
        require_locators("Pessoa vai tomar posse (PSD)", ("Pessoa tomou posse (PSDB)",))


def test_pdf_linebreak_hyphens_do_not_lose_source_party():
    require_locators("Clécio Luís, do Solida-\nriedade", ("Clécio Luís, do Solidariedade",))


def test_reviewed_transcription_never_fingerprints_unavailable_original(tmp_path):
    record = es_reviewed_observation(tmp_path)
    proof = record["evidence"][0]
    assert proof["sha256_scope"] == "reviewed_transcription"
    assert proof["original_document_sha256"] is None
    assert record["source_observed_on"] == "2023-04-12"
    assert record["political_party_status"] == "unknown"
    assert Path(proof["reviewed_transcription_path"]).exists()


def test_office_observation_does_not_become_inauguration():
    record = annual_observation(
        artifact(), "governo de Pessoa (PSB)", uf="MA", name="Pessoa", party="PSB",
        locators=("governo de Pessoa (PSB)",), kind="office_observation",
        observed_on="2023-02-28", published_on="2023-02-28",
    )
    assert record["political_party_status"] == "verified_official_dated_government_observation"
    assert record["source_observed_on"] == "2023-02-28"
    assert record["political_party_context"] == "party_reported_during_government"


def test_historical_inauguration_preserves_year_and_party_then_instead_of_current_party():
    record = annual_observation(
        artifact(), "Ronaldo Caiado (DEM) assumiu o governo de Goiás", uf="GO",
        name="Ronaldo Caiado", party="DEM",
        locators=("Ronaldo Caiado (DEM) assumiu o governo de Goiás",),
        observed_on="2019-01-01", published_on="2019-01-02",
    )
    assert record["year_start"] == record["year_end"] == 2019
    assert record["political_party_year_start"] == record["political_party_year_end"] == 2019
    assert record["political_party_abbreviation"] == "DEM"


def test_historical_signatures_are_not_inaugurations_or_continuous_affiliation(tmp_path):
    rows = reviewed_2019_office_records(tmp_path)
    signatures = [r for r in rows if r["observation_kind"] == "historical_signature_observation"]
    assert len(signatures) == 6
    assert all(r["source_observed_on"] == "2019-11-28" for r in signatures)
    assert all(r["political_party_status"] == "unknown" for r in signatures)
    assert all(r["evidence"][0]["original_document_sha256"] is None for r in signatures)
    assert all(r["evidence"][0]["published_on"] == "2025-09-17" for r in signatures)


def test_multiple_observations_of_one_uf_never_count_as_more_territories():
    records = [{"territory_code": "MG", "year_start": 2023}] * 27
    coverage = observation_coverage(records)
    assert coverage["uf_count"] == 1
    assert coverage["complete"] is False


def test_html_response_cannot_masquerade_as_official_newspaper_pdf(tmp_path):
    path = tmp_path / "official.pdf"
    path.write_bytes(b"<html>Unavailable during election period</html>")
    with pytest.raises(IngestionError, match="GOVERNOR_NEWSPAPER_NOT_PDF"):
        newspaper_text(path)


def test_reviewed_district_observation_cannot_become_state_government(tmp_path):
    from service.national_government_history.reviewed_legal_observations import (
        reviewed_office_record,
    )

    record = reviewed_office_record(
        tmp_path, uf="DF", name="Celina Leão", text="atual governadora do DF",
        url="https://www.tse.jus.br/fixture", observed="2026-10-04", published="2026-10-04",
        kind="office_observation", political_party="PP",
    )
    assert record["institution_code"] == "district_government"
    assert record["year_start"] == record["year_end"] == 2026
    assert record["starts_on"] is None and record["ends_before"] is None
    assert record["evidence"][0]["original_document_sha256"] is None


def test_interim_governor_stays_an_acting_dated_observation():
    record = annual_observation(
        artifact(), "Pessoa assume interinamente o Governo", uf="RR", name="Pessoa",
        party=None, locators=("Pessoa assume interinamente o Governo",),
        observed_on="2026-04-30", published_on="2026-04-30",
    )
    assert record["exercise_capacity"] == "acting"
    assert record["starts_on"] is None and record["ends_before"] is None
    assert record["political_party_status"] == "unknown"


def test_party_self_statement_never_becomes_government_membership_certificate():
    from service.national_government_history.party_2026 import qualify_party_statement

    record = annual_observation(
        artifact(), "Governador Pessoa (PSD)", uf="RS", name="Pessoa", party="PSD",
        locators=("Governador Pessoa (PSD)",), observed_on="2026-03-23",
    )
    qualify_party_statement(record)
    assert record["political_party_status"] == "verified_party_official_dated_government_statement"
    assert record["evidence"][0]["source_kind"] == "political_party_official_reporting"
    assert "not_government_membership_certificate" in record["political_party_limitation"]
    assert record["political_party_year_start"] == record["political_party_year_end"] == 2026


def test_reviewed_party_fallback_retains_qualification_and_original_hash_gap(tmp_path):
    from service.national_government_history.party_2026 import PARTY_STATEMENT_URLS
    from service.national_government_history.reviewed_current_2026 import reviewed_2026_fallback

    records = reviewed_2026_fallback(tmp_path, PARTY_STATEMENT_URLS)
    assert {r["territory_code"] for r in records} == {"AM", "MS", "RS"}
    for record in records:
        assert record["political_party_status"] == (
            "verified_party_official_dated_government_statement"
        )
        assert record["evidence"][0]["sha256_scope"] == "reviewed_transcription"
        assert record["evidence"][0]["original_document_sha256"] is None
