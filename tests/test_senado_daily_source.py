"""Private daily inputs resolve UUIDs and reuse immutable source acquisition."""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from service.voting_pipeline.source_senado import normalize_senate_source_files


class FakeAcquisition:
    def __init__(self, voting_rows):
        self.voting_rows = voting_rows
        self.calls = []

    def json_document(self, path, kind):
        self.calls.append((path, kind))
        artifact = SimpleNamespace(sha256="a" * 64, fetched_at="2026-10-17T12:00:00+00:00")
        if path.startswith("processo/"):
            return {
                "id": 123,
                "sigla": "PL",
                "numero": "1",
                "ano": 2026,
                "conteudo": {"ementa": "Ementa oficial demonstrativa."},
            }, artifact
        return self.voting_rows, artifact


class CachedProfiles:
    def extend_resolved_index(self, *args):
        pass

    def summary(self):
        return {"profile_acquisition_attempts": 0}


def voting(key=1, voter="42"):
    return {
        "codigoSessaoVotacao": key,
        "dataSessao": "2026-10-01",
        "idProcesso": 123,
        "codigoMateria": 456,
        "votacaoSecreta": "N",
        "sigla": "PL",
        "numero": "1",
        "ano": 2026,
        "identificacao": "PL 1/2026",
        "descricaoVotacao": "Texto em primeiro turno",
        "votos": [{"codigoParlamentar": voter, "siglaVotoParlamentar": "Sim"}],
    }


def test_shared_process_cached_identity_and_private_whitelist(tmp_path):
    from service.analytical_datasets.contracts import VOTE_COLUMNS
    from service.analytical_datasets.public_voting_timeline import MATTER_INPUT_COLUMNS

    acquisition = FakeAcquisition([voting(1), voting(2)])
    person_id = str(uuid4())
    path = tmp_path / "votes.ndjson"
    result = normalize_senate_source_files(
        None,
        acquisition,
        [(date(2026, 10, 1), date(2026, 10, 17))],
        path,
        {"42": (person_id, "b" * 64)},
        CachedProfiles(),
    )
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    assert len([call for call in acquisition.calls if call[1] == "process"]) == 1
    assert records[0]["voting_id"] == "senado:plenary:1"
    assert records[0]["person_id"] == person_id
    assert records[0]["description"] == "Ementa oficial demonstrativa."
    assert records[0]["description_origin"] == "official_text"
    assert records[0]["round_number"] == 1
    assert records[0]["official_url"] == (
        "https://www25.senado.leg.br/web/atividade/materias/-/materia/456/votacoes"
    )
    assert set(records[0]) == VOTE_COLUMNS | MATTER_INPUT_COLUMNS | {"source_observed_at"}
    assert result["receipts"][0]["collection_complete"] is False
    assert result["evidence_dependencies"] == ["a" * 64, "b" * 64]
    assert "codigoParlamentar" not in path.read_text()
    assert result["profile_acquisition_attempts"] == 0


@pytest.mark.parametrize("matter_code", [None, "", "invalid", "0", "-1", "٤٥٦"])
def test_nominal_link_never_substitutes_a_process_id_for_a_matter_code(matter_code):
    from service.voting_pipeline.source_senado import nominal_voting_url

    assert nominal_voting_url({"idProcesso": 123, "codigoMateria": matter_code}) is None


def test_missing_identity_and_description_budget_remain_partial(tmp_path):
    acquisition = FakeAcquisition([voting(1), voting(2, voter="404")])
    result = normalize_senate_source_files(
        None,
        acquisition,
        [(date(2026, 10, 1), date(2026, 10, 17))],
        tmp_path / "votes.ndjson",
        {"42": (str(uuid4()), "b" * 64)},
        CachedProfiles(),
        max_processes=0,
    )
    assert result["rows"] == 1
    assert result["identity_unresolved"] == 1
    assert result["description_missing"] == 1
    assert result["status"] == "partial"
    assert all(kind != "process" for _, kind in acquisition.calls)
    row = json.loads((tmp_path / "votes.ndjson").read_text())
    assert row["description"] is None and row["description_origin"] == "unknown"


def test_output_budget_does_not_replace_previous_snapshot(tmp_path, monkeypatch):
    import service.voting_pipeline.source_senado as source

    path = tmp_path / "votes.ndjson"
    path.write_text("previous")
    monkeypatch.setattr(source, "MAX_INPUT_BYTES", 1)
    with pytest.raises(Exception, match="INPUT_LIMIT"):
        normalize_senate_source_files(
            None,
            FakeAcquisition([voting()]),
            [(date(2026, 10, 1), date(2026, 10, 17))],
            path,
            {"42": (str(uuid4()), "b" * 64)},
            CachedProfiles(),
        )
    assert path.read_text() == "previous"


def test_invalid_budget_stops_before_source_or_database_access(tmp_path):
    from service.voting_pipeline.source_senado import collect_senate_source_files

    with pytest.raises(Exception, match="BUDGET"):
        collect_senate_source_files(
            None,
            tmp_path,
            date(2026, 10, 1),
            date(2026, 10, 17),
            tmp_path / "votes.ndjson",
            max_processes=101,
        )


def test_repeat_cached_acquisition_keeps_same_observation_and_input_hash(tmp_path):
    acquisition = FakeAcquisition([voting()])
    identities = {"42": (str(uuid4()), "b" * 64)}
    summaries = [
        normalize_senate_source_files(
            None,
            acquisition,
            [(date(2026, 10, 1), date(2026, 10, 17))],
            tmp_path / "votes.ndjson",
            identities,
            CachedProfiles(),
        )
        for _ in range(2)
    ]
    assert summaries[0]["input_sha256"] == summaries[1]["input_sha256"]
    assert summaries[0]["receipts"] == summaries[1]["receipts"]


def test_source_lock_is_released_after_cooldown_failure(tmp_path, monkeypatch):
    import service.voting_pipeline.runtime as runtime
    from crawlers.senado.configuration import OFFICIAL_HOSTS, SOURCE, SenateConfiguration
    from service.ingestion.contracts import IngestionError

    calls = []

    class Connection:
        def execute(self, query, params):
            calls.append(query)
            return SimpleNamespace(fetchone=lambda: {"acquired": True})

    def cooldown(*args):
        raise IngestionError("SOURCE_COOLDOWN_ACTIVE")

    monkeypatch.setattr(runtime, "check_source_cooldown", cooldown)
    with (
        pytest.raises(IngestionError, match="COOLDOWN"),
        runtime.official_source_acquisition(
            Connection(), SenateConfiguration(tmp_path), SOURCE, OFFICIAL_HOSTS, FakeAcquisition
        ),
    ):
        raise AssertionError("A cooldown must not permit acquisition")
    assert "pg_try_advisory_lock" in calls[0]
    assert "pg_advisory_unlock" in calls[-1]


def test_real_acquisition_cache_avoids_repeat_http(tmp_path):
    import httpx

    from crawlers.senado.acquisition import SenateAcquisition
    from crawlers.senado.configuration import OFFICIAL_HOSTS, SenateConfiguration
    from service.acquisition.http_client import OfficialHttpClient

    requests = []

    def respond(request):
        requests.append(request.url.path)
        payload = (
            {
                "id": 123,
                "sigla": "PL",
                "numero": "1",
                "ano": 2026,
                "conteudo": {"ementa": "Ementa oficial."},
            }
            if "/processo/" in request.url.path
            else [voting()]
        )
        return httpx.Response(200, json=payload)

    configuration = SenateConfiguration(tmp_path / "source")
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        acquisition = SenateAcquisition(
            configuration, OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
        )
        identities = {"42": (str(uuid4()), "b" * 64)}
        for _ in range(2):
            normalize_senate_source_files(
                None,
                acquisition,
                [(date(2026, 10, 1), date(2026, 10, 17))],
                tmp_path / "votes.ndjson",
                identities,
                CachedProfiles(),
            )
    assert len(requests) == 2
    assert sum("/processo/" in path for path in requests) == 1


def test_corrected_ementa_uses_process_observation_time(tmp_path):
    class CorrectedProcess(FakeAcquisition):
        observed_at = "2026-10-17T13:00:00+00:00"
        text = "Ementa anterior."

        def json_document(self, path, kind):
            payload, artifact = super().json_document(path, kind)
            if kind == "process":
                payload["conteudo"]["ementa"] = self.text
                artifact = SimpleNamespace(
                    sha256=("c" if self.text.endswith("corrigida.") else "a") * 64,
                    fetched_at=self.observed_at,
                )
            return payload, artifact

    source = CorrectedProcess([voting()])
    path = tmp_path / "votes.ndjson"
    identities = {"42": (str(uuid4()), "b" * 64)}
    arguments = (
        None,
        source,
        [(date(2026, 10, 1), date(2026, 10, 17))],
        path,
        identities,
        CachedProfiles(),
    )
    first = normalize_senate_source_files(*arguments)
    before = json.loads(path.read_text())
    source.text, source.observed_at = "Ementa corrigida.", "2026-10-18T13:00:00+00:00"
    second = normalize_senate_source_files(*arguments)
    after = json.loads(path.read_text())
    assert before["source_observed_at"] == "2026-10-17T13:00:00+00:00"
    assert after["source_observed_at"] == "2026-10-18T13:00:00+00:00"
    assert after["description"] == "Ementa corrigida."
    assert first["input_sha256"] != second["input_sha256"]
    assert "c" * 64 in second["evidence_dependencies"]


def test_explicit_secret_correction_emits_metadata_without_individual_votes(tmp_path):
    secret = voting() | {"votacaoSecreta": "S"}
    path = tmp_path / "votes.ndjson"
    result = normalize_senate_source_files(
        None,
        FakeAcquisition([secret]),
        [(date(2026, 10, 1), date(2026, 10, 17))],
        path,
        {"42": (str(uuid4()), "b" * 64)},
        CachedProfiles(),
    )
    assert result["rows"] == 0
    assert path.read_text() == ""
    assert result["explicit_secret_voting_keys"] == ["senado:plenary:1"]
    assert result["explicit_secret_votings"] == [
        {
            "voting_id": "senado:plenary:1",
            "occurred_on": "2026-10-01",
            "source_observed_at": "2026-10-17T12:00:00+00:00",
        }
    ]
    metadata = json.loads(path.with_suffix(".ndjson.manifest.json").read_text())
    assert metadata["explicit_secret_voting_keys"] == ["senado:plenary:1"]
    assert metadata["collection_complete"] is False


def test_profile_evidence_correction_updates_source_observation(tmp_path):
    path = tmp_path / "votes.ndjson"
    normalize_senate_source_files(
        None,
        FakeAcquisition([voting()]),
        [(date(2026, 10, 1), date(2026, 10, 17))],
        path,
        {"42": (str(uuid4()), "b" * 64)},
        CachedProfiles(),
        identity_observations={"b" * 64: "2026-10-19T13:00:00+00:00"},
    )
    assert json.loads(path.read_text())["source_observed_at"] == "2026-10-19T13:00:00+00:00"


def test_backfill_reuses_official_original_ementa_without_process_downloads(tmp_path):
    raw = voting() | {"ementa": "Ementa publicada na votação oficial."}
    acquisition = FakeAcquisition([raw])
    result = normalize_senate_source_files(
        None,
        acquisition,
        [(date(2026, 10, 1), date(2026, 10, 1))],
        tmp_path / "backfill.ndjson",
        {"42": (str(uuid4()), "b" * 64)},
        CachedProfiles(),
        max_processes=0,
    )
    record = json.loads((tmp_path / "backfill.ndjson").read_text())
    assert record["description"] == raw["ementa"]
    assert record["description_origin"] == "official_text"
    assert result["processes_acquired"] == 0
    assert len(acquisition.calls) == 1


def test_unpublished_nominal_list_does_not_fail_the_whole_historical_month(tmp_path):
    raw = voting() | {"votos": None}
    acquisition = FakeAcquisition([raw])
    result = normalize_senate_source_files(
        None,
        acquisition,
        [(date(2026, 10, 1), date(2026, 10, 1))],
        tmp_path / "unavailable.ndjson",
        {},
        CachedProfiles(),
        max_processes=0,
    )
    assert result["rows"] == 0
    assert result["receipts"][0]["votings"] == 1
    assert result["collection_complete"] is False
    from crawlers.senado.legislative_voting import normalize_voting_record

    normalized = normalize_voting_record(raw)
    assert normalized["nominal_availability"] == "unavailable"
    assert normalized["nominal_votes"] == []
