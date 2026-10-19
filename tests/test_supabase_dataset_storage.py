import httpx
import pytest
from test_daily_voting_dataset import partition, publish, row

from service.dataset_storage.supabase import StorageConfiguration, SupabaseDatasetStorage


def test_manifest_is_uploaded_last_and_bucket_remains_private(tmp_path):
    manifest = publish(tmp_path, [row()])
    directory = tmp_path / "derived" / partition().relative_path
    requests = []

    def respond(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"public": False})
        return httpx.Response(200, json={})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        storage = SupabaseDatasetStorage(
            StorageConfiguration("https://example.supabase.co", "secret"), client
        )
        result = storage.publish_daily_manifest(directory, partition().relative_path, manifest)
    assert result["published"] is True
    assert requests[0][0] == "GET"
    assert requests[-1][1].endswith("/manifest.json")
    assert len(requests) == 4


def test_failed_private_upload_never_activates_remote_manifest(tmp_path):
    manifest = publish(tmp_path, [row()])
    requests = []

    def respond(request):
        requests.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={"public": False})
        return httpx.Response(
            500 if request.url.path.endswith(".private.parquet") else 200, json={}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        storage = SupabaseDatasetStorage(
            StorageConfiguration("https://example.supabase.co", "secret"), client
        )
        with pytest.raises(httpx.HTTPStatusError):
            storage.publish_daily_manifest(
                tmp_path / "derived" / partition().relative_path,
                partition().relative_path,
                manifest,
            )
    assert not any(path.endswith("manifest.json") for path in requests)


def test_public_bucket_is_not_used_for_private_checkpoint():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"public": True}))
    ) as client:
        storage = SupabaseDatasetStorage(
            StorageConfiguration("https://example.supabase.co", "secret"), client
        )
        with pytest.raises(ValueError, match="private bucket"):
            storage.ensure_private_bucket()


def test_credentials_are_not_in_configuration_repr():
    configuration = StorageConfiguration("https://example.supabase.co", "private-token")
    assert "private-token" not in repr(configuration)
