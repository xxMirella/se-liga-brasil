"""Official gallery roles, temporal precision and publication conflicts stay explicit."""

from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.municipal_government.fortaleza_gallery import fortaleza_annual_exercise
from crawlers.state_government.republican_gallery import parana_gallery_block
from service.government_gallery_history.publication import preserve_existing_observations
from service.political_dashboard_dataset.executive import build_annual_executive_partitions


def artifact():
    return SimpleNamespace(resource=SimpleNamespace(url='https://www.casacivil.pr.gov.br/source'),
                           sha256='a' * 64, fetched_at='2026-10-26T12:00:00+00:00')


def test_vice_governor_term_does_not_prove_exercise_of_government():
    rows, reviews = parana_gallery_block(
        'Vice apenas', 'Vice-Governador\n01.01.2011 a 31.12.2014', artifact(),
    )
    assert rows == []
    assert reviews[0]['reason'] == 'vice_or_collective_not_individual_exercise'


def test_successor_has_only_governor_dates_and_preserves_year_end_inclusive():
    rows, _ = parana_gallery_block(
        'Sucessora', 'Vice-Governadora\nGovernadora\n'
        '01.01.2015 a 06.04.2018\n06.04.2018 a 31.12.2018', artifact(),
    )
    assert len(rows) == 1
    assert rows[0]['starts_on'] == '2018-04-06'
    assert rows[0]['ends_before'] == '2019-01-01'
    assert rows[0]['political_party_status'] == 'unknown'


def test_uncertain_source_dates_are_rejected_instead_of_invented():
    rows, reviews = parana_gallery_block(
        'Pessoa', 'Presidente do Estado\n25.02.1892 (?) a 12.04.1893', artifact(),
    )
    assert rows == []
    assert reviews[0]['reason'] == 'uncertain_dates_or_open_vice_office'


def test_annual_municipal_interval_preserves_identity_and_no_day_snapshot():
    row = fortaleza_annual_exercise(artifact(), 'Gestora', 2005, 2012, '2005–2012')
    partition = build_annual_executive_partitions([row], 2008, date(2026, 10, 26))[0]
    assert row['municipality_ibge'] == '2304400'
    assert row['represented_uf'] == 'CE'
    assert row['territorial_boundaries_reconstructed'] is False
    assert partition['snapshot_on'] is None
    assert partition['current'] is None
    assert partition['segments'][0]['date_precision'] == 'year'
    assert partition['segments'][0]['political_party_status'] == 'unknown'
    assert build_annual_executive_partitions([row], 2013, date(2026, 10, 26)) == []


def test_richer_existing_projection_is_never_silently_replaced():
    with pytest.raises(ValueError, match='REQUIRES_SOURCE_RECONCILIATION'):
        preserve_existing_observations({'segments': []}, {'current': {'name': 'Original'}})


def test_repeated_publication_preserves_dated_observations_without_duplicate_segments():
    incoming = {'aggregation_basis': 'official_gallery_exercises_overlapping_year',
                'segments': [{'name': 'Governante'}]}
    existing = {**incoming, 'national_observations': [{'name': 'Observação oficial'}]}
    merged = preserve_existing_observations(incoming, existing)
    assert merged['segments'] == incoming['segments']
    assert merged['national_observations'] == existing['national_observations']


def test_goias_collective_government_is_one_exercise_with_documented_members():
    from crawlers.state_government.goias_gallery import (
        combine_documented_juntas,
        goias_gallery_exercise,
    )

    rows = [goias_gallery_exercise([name, 'Junta Governativa', '07/12/1889', '24/02/1890'],
                                   artifact()) for name in ['Membro A', 'Membro B', 'Membro C']]
    result = combine_documented_juntas(rows)
    assert len(result) == 1
    assert result[0]['exercise_capacity'] == 'collective_junta'
    assert len(result[0]['collective_members']) == 3
    assert len(result[0]['evidence']) == 3


def test_goias_open_government_is_bounded_by_source_update_not_today():
    from crawlers.state_government.goias_gallery import goias_gallery_exercise

    row = goias_gallery_exercise(['Governante', 'Governador', '01/04/2026', ''], artifact())
    partition = build_annual_executive_partitions([row], 2026, date(2026, 10, 26))[0]
    assert row['observed_through'] == '2026-07-10'
    assert partition['current'] is None
    assert partition['snapshot_on'] is None
