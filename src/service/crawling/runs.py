"""Reusable database run lifecycle for every source pipeline."""

from dataclasses import asdict
from uuid import uuid4


def execute_ingestion_run(command, configuration, transport, repository, *, pipeline) -> dict:
    configuration_payload = asdict(configuration)
    configuration_payload["storage_directory"] = str(configuration.storage_directory)
    repository.begin_run(str(uuid4()), configuration_payload)
    try:
        result = pipeline(command, configuration, transport, repository)
        has_rejections = any(artifact["rejected"] for artifact in result.get("artifacts", []))
        status = (
            "partial"
            if result.get("failures") or has_rejections or result.get("identity_unresolved")
            else "completed"
        )
        repository.finish_run(status, result)
        return result | {"status": status}
    except BaseException:
        repository.finish_run("failed", {})
        raise
