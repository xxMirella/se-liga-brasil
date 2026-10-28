"""An unavailable preview cannot be reported as a failed government data source."""

import importlib.util
import io
import json
from pathlib import Path

from storage.files import save_json


def test_http_transport_failure_keeps_api_error_instead_of_inventing_source_pending(tmp_path):
    path = Path(__file__).parents[1] / "scripts" / "audit_state_assembly_coverage.py"
    spec = importlib.util.spec_from_file_location("assembly_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    save_json(tmp_path / "investigation-notes.json", {"AL": {"reason": "old_pending_reason"}})
    rows = [{"uf": "AL", "status": "api_error", "error": "URLError"}]
    module.attach_investigation_evidence(rows, tmp_path)
    assert rows[0]["status"] == "api_error"
    assert "investigation" not in rows[0]


def test_published_reconciliation_retains_qualification_and_null_snapshot(monkeypatch):
    path = Path(__file__).parents[1] / "scripts" / "audit_state_assembly_coverage.py"
    spec = importlib.util.spec_from_file_location("assembly_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = {
        "assembly": {
            "institution_code": "alego",
            "total": 41,
            "coverage": "observed_partial",
            "aggregation_basis": "official_roster_reconciled_with_dated_exercise_evidence",
            "snapshot_on": None,
            "reconciled_records_count": 41,
            "last_exercise_evidence_on": "2026-10-07",
            "political_parties": [],
        }
    }
    response = io.BytesIO(json.dumps(payload).encode())
    response.status = 200
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: response)
    row = module.inspect_state("http://127.0.0.1:8787", "GO")
    assert row["status"] == "published"
    assert row["coverage"] == "observed_partial"
    assert row["snapshot_on"] is None
    assert row["reconciled_records_count"] == 41
    assert row["last_exercise_evidence_on"] == "2026-10-07"
