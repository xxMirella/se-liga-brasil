"""Validate cached official galleries and publish bounded annual executive history."""

import argparse
import json
from datetime import date
from pathlib import Path

from database.operations import connect_database
from service.government_gallery_history.collection import normalize_official_galleries
from service.government_gallery_history.publication import publish_official_gallery_records
from storage.files import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-manifests', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--storage', type=Path, default=Path('data/political-dashboard'))
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--activate', action='store_true')
    options = parser.parse_args()
    manifests = json.loads(options.source_manifests.read_text())
    records, source_reviews = normalize_official_galleries(manifests, date.today())
    if not records:
        raise ValueError('NO_VERIFIED_GOVERNMENT_GALLERY_RECORDS')
    save_json(options.report.with_suffix('.evidence.json'), {
        'schema_version': 'historical_executive_evidence.v1', 'exercises': records,
        'coverage': 'documented_partial', 'canonical_person_linking': 'not_attempted',
        'limitations': ['party_affiliations_not_inferred', 'annual_precision_preserved',
                       'municipal_territorial_boundaries_not_reconstructed'],
    })
    with connect_database(options.env_file) as connection:
        publication = publish_official_gallery_records(
            connection, records, options.storage, date.today(), activate=options.activate,
        )
    report = {'reviewed_on': str(date.today()), 'records': len(records),
              'source_reviews': source_reviews, 'publication': publication,
              'source_errors': {key: row for key, row in manifests.items() if row.get('error')}}
    save_json(options.report, report)
    print(json.dumps({'records': len(records), **publication}, ensure_ascii=False))


if __name__ == '__main__':
    main()
