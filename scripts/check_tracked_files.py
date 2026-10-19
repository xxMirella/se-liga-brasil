"""Run in the CI checkout; report prohibited paths without reading their values."""

import subprocess

from code_quality.private_files import private_tracked_paths


def main():
    result = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True)
    paths = [value for value in result.stdout.decode("utf-8").split("\0") if value]
    rejected = private_tracked_paths(paths)
    for path in rejected:
        print("Private file cannot be versioned: " + path)
    return int(bool(rejected))


if __name__ == "__main__":
    raise SystemExit(main())
