"""Vercel build gate: check database-backed routes without emitting credentials."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from service.deployment_validation.public_portal import (  # noqa: E402
    DeploymentValidationError,
    check_public_search,
)


def main():
    try:
        result = check_public_search()
    except DeploymentValidationError as error:
        print(json.dumps({"status": "failed", "code": str(error)}))
        return 1
    except Exception as error:
        print(json.dumps({
            "status": "failed", "code": "PUBLIC_SEARCH_CHECK_FAILED",
            "error_type": type(error).__name__,
        }))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
