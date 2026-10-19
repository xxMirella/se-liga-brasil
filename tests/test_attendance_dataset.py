import json

from service.analytical_datasets.storage import connect_analytical_engine
from service.attendance.dataset import publish_attendance_month


class SuccessfulResponse:
    def raise_for_status(self):
        pass


class RecordingStorage:
    def __init__(self):
        self.objects = []

    def upload_immutable(self, key, path, digest):
        assert path.exists()
        self.objects.append((key, digest))

    def object_path(self, key):
        return key

    def request(self, method, path, **arguments):
        assert method == "POST"
        assert self.objects
        assert json.loads(arguments["content"])["row_count"] == 1
        return SuccessfulResponse()


def test_monthly_parquet_is_readable_and_replay_has_same_content(tmp_path):
    storage = RecordingStorage()
    records = [{"personId": "00000000-0000-0000-0000-000000000001", "period": "2024-01",
                "required": 10, "present": 8, "percentage": "80.0"}]
    first = publish_attendance_month(tmp_path, storage, "2024-01", records)
    second = publish_attendance_month(tmp_path, storage, "2024-01", records)
    assert first == second
    assert len(storage.objects) == 1
    path = tmp_path / "attendance/camara/year=2024/month=01" / first["parquet_file"]
    with connect_analytical_engine(tmp_path / "temporary") as engine:
        row = engine.execute(
            "SELECT present, required FROM read_parquet(?)", [str(path)]
        ).fetchone()
    assert row == (8, 10)
