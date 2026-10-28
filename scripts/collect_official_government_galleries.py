"""Acquire bounded official galleries with immutable hashes for annual publication."""

import argparse
from pathlib import Path

import httpx

from crawlers.municipal_government.acquisition import (
    MunicipalGovernmentAcquisition,
    MunicipalGovernmentConfiguration,
)
from crawlers.state_government.acquisition import (
    StateGovernmentAcquisition,
    StateGovernmentConfiguration,
)
from service.ingestion.contracts import IngestionError
from storage.files import save_json

SOURCES = (
    ('pr', 'PR', 'https://www.casacivil.pr.gov.br/Pagina/Governantes-no-Periodo-Republicano'),
    ('go', 'GO', 'https://goias.gov.br/casacivil/governantes-republica/'),
    ('fortaleza', 'CE', 'https://fortalezaembairros.fortaleza.ce.gov.br/gestores'),
)


def collect_galleries(client):
    state = StateGovernmentAcquisition(
        StateGovernmentConfiguration(Path('data/state-government-history')), client)
    municipal = MunicipalGovernmentAcquisition(
        MunicipalGovernmentConfiguration(Path('data/municipal-government-history')), client)
    manifests = {}
    for key, uf, url in SOURCES:
        try:
            artifact = (municipal if key == 'fortaleza' else state).acquire(url, uf)
            manifests[key] = {'source_url': url, 'uf': uf, 'path': str(artifact.path),
                              'sha256': artifact.sha256, 'fetched_at': artifact.fetched_at}
        except IngestionError as error:
            manifests[key] = {'source_url': url, 'uf': uf, 'error': error.code}
    return manifests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    with httpx.Client() as client:
        manifests = collect_galleries(client)
    save_json(options.output, manifests)
    print({key: 'error' if row.get('error') else 'archived' for key, row in manifests.items()})


if __name__ == '__main__':
    main()
