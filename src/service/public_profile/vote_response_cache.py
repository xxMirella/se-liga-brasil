"""In-process cache of the final vote/history response of one person.

Key = person + normalized request parameters + calendar day + dataset version (a cheap
fingerprint of the published-partition catalog), so a newly published day never serves a
stale page. Errors are never stored: PublicSearchCache only stores what the loader returned.
"""

from service.dataset_storage.catalog import catalog_version, published_partitions
from service.dataset_storage.read import DatasetReadError
from service.public_profile.contracts import PublicProfileError
from service.public_profile.search_cache import PublicSearchCache

RESPONSE_TTL_SECONDS = 120
RESPONSE_CAPACITY = 256
RESPONSE_MAX_BYTES = 4 * 1024 * 1024  # responses are ~5 KB; this holds hundreds of people


def warm_published_partitions(reader):
    """Memoized catalog load; Storage failures become public errors, not 400s."""
    try:
        published_partitions(reader)
    except DatasetReadError as error:
        raise PublicProfileError(error.code, error.status_code) from error


class VoteResponseCache:
    def __init__(self, reader, *, ttl_seconds=RESPONSE_TTL_SECONDS, capacity=RESPONSE_CAPACITY,
                 max_bytes=RESPONSE_MAX_BYTES, clock=None):
        self.reader = reader
        options = {"clock": clock} if clock is not None else {}
        self.cache = PublicSearchCache(
            ttl_seconds=ttl_seconds, capacity=capacity, max_bytes=max_bytes, **options
        )

    def clear(self):
        self.cache.clear()

    def get_or_load(self, person_id, parameters, day, load, *, warm_catalog=False,
                    dataset_reader=None):
        """warm_catalog: history reads need the catalog anyway, so load it before keying.

        dataset_reader: the reader in effect for this call. Serverless applications create the
        authenticated Storage reader lazily, after this cache was built without one, so the
        caller passes the current reader; it falls back to the one given at construction.
        """
        reader = dataset_reader if dataset_reader is not None else self.reader
        if warm_catalog and reader is not None:
            warm_published_partitions(reader)
        key = (
            "votes", str(person_id), tuple(sorted((str(k), str(v)) for k, v in parameters.items())),
            str(day), catalog_version(reader),
        )
        produced = []

        def tracked():
            produced.append(load())
            return produced[0]

        try:
            return self.cache.get_or_load(key, tracked)
        except (TypeError, ValueError):
            if produced:  # not JSON-serializable: serve it uncached rather than fail
                return produced[0]
            raise
