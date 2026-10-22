import pytest

from crawlers.camara.normalization import continuous_exercise_start


def event(day, state='Exercício'):
    return {'dataHora': day + 'T12:00', 'situacao': state}


def test_party_updates_and_duplicate_rows_do_not_restart_exercise():
    history = [event('2025-01-01'), event('2023-02-01'), event('2025-01-01')]
    assert continuous_exercise_start(history) == '2023-02-01'


def test_return_after_leave_starts_a_new_continuous_exercise():
    history = [event('2023-02-01'), event('2024-01-01', 'Licença'),
               event('2024-04-01'), event('2025-01-01')]
    assert continuous_exercise_start(history) == '2024-04-01'


@pytest.mark.parametrize('history', [[], [event('2025-01-01', 'Licença')],
    [event('2023-02-01'), event('2025-01-01'), event('2025-01-01', 'Licença')]])
def test_absent_or_conflicting_latest_state_does_not_fabricate_start(history):
    assert continuous_exercise_start(history) is None
