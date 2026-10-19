"""Fail CI on structural findings; never load a production environment file."""

from pathlib import Path

from code_quality.environment_contract import validate_environment_template
from code_quality.system_design import review_project


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    validate_environment_template(root)
    findings = review_project(root)
    for finding in findings:
        print(f"{finding['path']}:{finding['line']}: {finding['rule']}: {finding['message']}")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
