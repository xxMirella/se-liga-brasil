"""Private source archives and environment files must not enter Git snapshots."""

import pytest

from code_quality.private_files import private_tracked_paths


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.storage",
        "config/.env.production",
        "data/archive.csv",
        "keys/id_rsa",
        "id_ed25519",
    ],
)
def test_private_local_paths_are_blocked(path):
    assert private_tracked_paths([path]) == [path]


@pytest.mark.parametrize(
    "path",
    [".env.example", "tests/.env.example", "tests/fixtures/data.csv", "src/database/operations.py"],
)
def test_examples_and_code_remain_versionable(path):
    assert private_tracked_paths([path]) == []
