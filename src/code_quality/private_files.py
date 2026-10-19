"""Reject private local state in version control using paths, never file contents."""

from pathlib import PurePosixPath


def private_tracked_paths(paths):
    rejected = []
    for value in paths:
        path = PurePosixPath(value)
        private_env = path.name.startswith(".env") and path.name != ".env.example"
        if private_env or path.parts[0] == "data" or path.name in {"id_rsa", "id_ed25519"}:
            rejected.append(value)
    return rejected
