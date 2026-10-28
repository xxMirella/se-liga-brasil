"""Validate archived official galleries and report source-specific gaps explicitly."""

from pathlib import Path

from crawlers.municipal_government.fortaleza_gallery import parse_fortaleza_government_gallery
from crawlers.state_government.goias_gallery import parse_goias_republican_gallery
from crawlers.state_government.republican_gallery import parse_parana_republican_gallery
from service.ingestion.contracts import DownloadedArtifact, Resource
from storage.files import hash_file


def archived_gallery_artifact(manifest):
    path = Path(manifest['path'])
    if hash_file(path) != manifest['sha256']:
        raise ValueError('GOVERNMENT_GALLERY_ARCHIVE_HASH_MISMATCH')
    resource = Resource('official-gallery', 'Official government gallery', manifest['source_url'],
                        'government_gallery', 1889, 'government-gallery-history', manifest['uf'])
    return DownloadedArtifact(resource, path, manifest['sha256'], manifest['fetched_at'],
                              path.stat().st_size, 'cached')


def normalize_official_galleries(manifests, observed_on):
    records, reviews = [], []
    for key in ('pr', 'fortaleza', 'go'):
        try:
            artifact = archived_gallery_artifact(manifests[key])
            if key == 'pr':
                parsed, rejected = parse_parana_republican_gallery(artifact)
            elif key == 'go':
                parsed, rejected = parse_goias_republican_gallery(artifact)
            else:
                parsed = parse_fortaleza_government_gallery(artifact, observed_on)
                rejected = []
            records.extend(parsed)
            reviews.append({'source': key, 'accepted': len(parsed), 'excluded': rejected})
        except (KeyError, ValueError, OSError) as error:
            reviews.append({'source': key, 'error': str(error)})
    return records, reviews
