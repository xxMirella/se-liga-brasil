"""Every served asset must be listed in package-data, or the deployed package serves a 503.

The production bundle is built from pyproject's package-data: a file missing there exists in the
repository and in local runs but not in production, where reading it raises. Scripts shipped that
way once, so the page had no animation and every filter reloaded the page.
"""

import tomllib
from fnmatch import fnmatch
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
PACKAGE_DATA = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"][
    "package-data"
]


def asset_files():
    return sorted(path for path in SOURCE.rglob("*") if "assets" in path.relative_to(SOURCE).parts
                  and path.is_file() and "__pycache__" not in path.parts)


def owning_package(path):
    directory = ".".join(path.relative_to(SOURCE).parent.parts)
    candidates = [name for name in PACKAGE_DATA if directory == name or
                  directory.startswith(name + ".")]
    return max(candidates, key=len) if candidates else None


@pytest.mark.parametrize("path", asset_files(), ids=lambda path: str(path.relative_to(SOURCE)))
def test_asset_is_listed_in_package_data(path):
    package = owning_package(path)
    assert package, f"no package-data entry covers {path.relative_to(SOURCE)}"
    package_directory = SOURCE.joinpath(*package.split("."))
    relative = path.relative_to(package_directory).as_posix()
    assert any(fnmatch(relative, pattern) for pattern in PACKAGE_DATA[package]), (
        f"{relative} is not matched by package-data of {package}: {PACKAGE_DATA[package]}"
    )
