"""Measure real public annual payloads and cache behavior without loading government APIs."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.public_cache import prepare_public_response  # noqa: E402
from application.public_portal import PublicPortalApplication, dispatch_portal_request  # noqa: E402


def measure_endpoint(application, target):
    started = time.perf_counter()
    response = dispatch_portal_request(application, target)
    cold_seconds = time.perf_counter() - started
    started = time.perf_counter()
    warm = dispatch_portal_request(application, target)
    warm_seconds = time.perf_counter() - started
    status, compressed, headers = prepare_public_response(
        target, response.status, response.body, {"Accept-Encoding": "gzip"}
    )
    payload = json.loads(response.body)
    return {
        "endpoint": target,
        "status": status,
        "cold_seconds": round(cold_seconds, 4),
        "warm_seconds": round(warm_seconds, 4),
        "json_bytes": len(response.body),
        "gzip_bytes": len(compressed),
        "etag": headers.get("ETag"),
        "cache_equal": warm.body == response.body,
        "year": payload.get("year"),
        "coverage": {
            name: payload.get(name, {}).get("coverage")
            for name in ["senate", "assembly", "presidency", "mayoralty"]
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    application = PublicPortalApplication(arguments.env_file, None)
    targets = [
        "/api/political-dashboard?level=federal&year=2026",
        "/api/political-dashboard?level=state&uf=SP&year=2026",
        "/api/political-dashboard?level=federal&year=1890",
        "/api/political-dashboard?level=municipal&uf=SP&municipality_ibge=3550308&year=2000",
    ]
    result = {"measurements": [measure_endpoint(application, target) for target in targets]}
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(content)
    print(content)


if __name__ == "__main__":
    main()
