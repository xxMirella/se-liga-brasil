"""Publish annual projections without replacing richer historical or dated observations."""

from database.government_gallery import existing_gallery_partitions
from database.political_dashboard_analytical import AnnualDashboardRepository
from service.political_dashboard_dataset.executive import build_annual_executive_partitions
from service.political_dashboard_dataset.executive_observations import (
    is_dated_observation_partition,
    merge_executive_observations,
)
from service.political_dashboard_dataset.storage import store_partition

BASIS = 'official_gallery_exercises_overlapping_year'


def gallery_partition_key(partition):
    return partition['year'], partition['territory_code'], partition['institution_code']


def preserve_existing_observations(incoming, existing):
    if not existing:
        return incoming
    if existing.get('aggregation_basis') == BASIS:
        return {**incoming, 'national_observations': existing.get('national_observations', [])}
    if not is_dated_observation_partition(existing):
        raise ValueError('EXISTING_HISTORICAL_PROJECTION_REQUIRES_SOURCE_RECONCILIATION')
    return merge_executive_observations(incoming, existing)


def prepare_gallery_partitions(records, existing, first_year, last_year, observed_on):
    partitions, errors = [], []
    for year in range(first_year, last_year + 1):
        for incoming in build_annual_executive_partitions(records, year, observed_on):
            incoming['aggregation_basis'] = BASIS
            key = gallery_partition_key(incoming)
            try:
                partitions.append(preserve_existing_observations(incoming, existing.get(key)))
            except ValueError as error:
                errors.append({'scope': key, 'error': str(error)})
    return partitions, errors


def publish_official_gallery_records(connection, records, storage, observed_on, *, activate):
    territories = {row['territory_code'] for row in records}
    existing = existing_gallery_partitions(connection, territories, 1889, observed_on.year)
    partitions, errors = prepare_gallery_partitions(records, existing, 1889, observed_on.year,
                                                   observed_on)
    if activate:
        AnnualDashboardRepository(connection).activate_partitions(partitions)
    entries = [store_partition(storage, row) for row in partitions]
    return {'partitions': len(partitions), 'new_partitions': sum(
        gallery_partition_key(row) not in existing for row in partitions),
        'total_bytes': sum(row['bytes'] for row in entries), 'errors': errors,
        'activated': activate}
