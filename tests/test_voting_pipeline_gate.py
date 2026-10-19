import json
from dataclasses import asdict
from datetime import date

import pytest
from test_daily_voting_dataset import row

from service.voting_pipeline.consolidation import consolidate_acquisition


class PublicationRecorder:
    def __init__(self, fail=False):
        self.manifests = []
        self.fail = fail

    def publish_daily_manifest(self, directory, relative_path, manifest):
        if self.fail:
            raise RuntimeError("storage unavailable")
        self.manifests.append(asdict(manifest))


def acquire(tmp_path, rows, *, secrets=()):
    incoming = tmp_path / "input.ndjson"
    incoming.write_text("".join(json.dumps(record) + "\n" for record in rows))
    return {
        "input_path": str(incoming),
        "parser_version": "test-v1",
        "explicit_secret_votings": list(secrets),
    }


def consolidate(tmp_path, result, publisher):
    temporary = tmp_path / "split"
    temporary.mkdir(exist_ok=True)
    for path in temporary.glob("*.ndjson"):
        path.unlink()
    return consolidate_acquisition(
        result,
        "senado",
        date(2026, 10, 14),
        date(2026, 10, 14),
        tmp_path / "datasets",
        temporary,
        publisher,
    )


def test_no_new_data_does_not_trigger_pipeline_or_storage(tmp_path):
    publisher = PublicationRecorder()
    record = row(occurred_on="2026-10-14")
    first = consolidate(tmp_path, acquire(tmp_path, [record]), publisher)
    assert first["pipeline_triggered"] is True
    assert len(publisher.manifests) == 1
    record["source_observed_at"] = "2026-10-20T12:00:00+00:00"
    replay = consolidate(tmp_path, acquire(tmp_path, [record]), publisher)
    assert replay["pipeline_triggered"] is False
    assert len(publisher.manifests) == 1
    corrected = row(
        occurred_on="2026-10-14", vote_choice="no", source_observed_at="2026-10-21T12:00:00+00:00"
    )
    assert consolidate(tmp_path, acquire(tmp_path, [corrected]), publisher)["pipeline_triggered"]
    assert len(publisher.manifests) == 2


def test_failed_storage_is_retried_and_empty_acquisition_does_not_erase(tmp_path):
    result = acquire(tmp_path, [row(occurred_on="2026-10-14")])
    with pytest.raises(RuntimeError, match="storage unavailable"):
        consolidate(tmp_path, result, PublicationRecorder(fail=True))
    publisher = PublicationRecorder()
    assert consolidate(tmp_path, result, publisher)["pipeline_triggered"] is True
    assert consolidate(tmp_path, acquire(tmp_path, []), publisher)["pipeline_triggered"] is False
    assert publisher.manifests[-1]["row_count"] == 1


def test_explicit_secret_correction_runs_even_without_nominal_rows(tmp_path):
    publisher = PublicationRecorder()
    record = row(occurred_on="2026-10-14")
    consolidate(tmp_path, acquire(tmp_path, [record]), publisher)
    retirement = {
        "voting_id": record["voting_id"],
        "occurred_on": "2026-10-14",
        "source_observed_at": "2026-10-22T12:00:00+00:00",
    }
    result = consolidate(tmp_path, acquire(tmp_path, [], secrets=[retirement]), publisher)
    assert result["pipeline_triggered"] is True
    assert publisher.manifests[-1]["row_count"] == 0
    assert not consolidate(tmp_path, acquire(tmp_path, [], secrets=[retirement]), publisher)[
        "pipeline_triggered"
    ]
