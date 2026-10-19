"""Streaming partition collection; persistence is an injected, batched consumer."""

from crawlers.transferegov.acquisition import partition_query
from crawlers.transferegov.normalization import NORMALIZERS
from service.ingestion.contracts import IngestionError


def collect_records(acquisition, module, endpoint, partitions):
    """Read each unique partition once; fail visibly instead of claiming full coverage."""
    seen_partitions = set()
    seen_records = {}
    normalizer = NORMALIZERS.get(endpoint)
    if normalizer is None:
        raise IngestionError("TRANSFEREGOV_UNSUPPORTED_DOMAIN")
    for filters in partitions:
        query = partition_query(module, endpoint, filters)
        if query in seen_partitions:
            continue
        if len(seen_partitions) >= acquisition.configuration.max_partitions:
            raise IngestionError("TRANSFEREGOV_PARTITION_LIMIT_EXCEEDED")
        seen_partitions.add(query)
        yield from collect_partition(
            acquisition, module, endpoint, filters, normalizer, seen_records
        )


def collect_partition(acquisition, module, endpoint, filters, normalizer, seen_records):
    for rows, artifact in acquisition.pages(module, endpoint, filters):
        for row in rows:
            normalized = select_unique_record(
                row, normalizer, seen_records, acquisition.configuration
            )
            if normalized is not None:
                yield normalized | {
                    "source_url": artifact.resource.url,
                    "source_sha256": artifact.sha256,
                    "observed_at": artifact.fetched_at,
                }


def select_unique_record(row, normalizer, seen_records, configuration):
    normalized = normalizer(row)
    key = normalized["record_key"]
    previous = seen_records.get(key)
    if previous is not None:
        if previous != normalized:
            raise IngestionError("TRANSFEREGOV_SNAPSHOT_CONFLICT")
        return None
    if len(seen_records) >= configuration.max_records:
        raise IngestionError("TRANSFEREGOV_RECORD_LIMIT_EXCEEDED")
    seen_records[key] = normalized
    return normalized
