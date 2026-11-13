"""Bounded, order-preserving parallel Storage reads (I/O bound, so threads are enough)."""

from concurrent.futures import ThreadPoolExecutor

MAX_READ_WORKERS = 6


def parallel_map(function, items, *, max_workers=MAX_READ_WORKERS):
    """Like map(), results in input order; the first failure in input order is raised.

    Nothing is returned (hence nothing can be cached) when any item fails.
    """
    items = list(items)
    if len(items) <= 1 or max_workers <= 1:
        return [function(item) for item in items]
    with ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as pool:
        return list(pool.map(function, items))
