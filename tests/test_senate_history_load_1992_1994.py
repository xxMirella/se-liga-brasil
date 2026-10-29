"""Rules of the 1992-1994 Senate load: no database, no network, fictitious people only."""

from datetime import date

import pytest
from senate_history_fixtures import (
    TERM_49_50,
    affiliation,
    build_plan,
    mandate,
)

from crawlers.senado.historical_period_normalization import (
    inclusive_end_to_exclusive,
    normalize_affiliations,
    normalize_identity,
)
from crawlers.senado.historical_period_rows import (
    person_id_for,
    qualified_abbreviation,
    storable_payload,
)
from crawlers.senado.historical_period_validation import ensure_disjoint, overlaps_window
from service.ingestion.contracts import IngestionError


def reasons(plan):
    return {(item.code, item.senator_id) for item in plan.pending}


def test_inclusive_last_day_becomes_exclusive_end():
    assert inclusive_end_to_exclusive("1993-06-15") == date(1993, 6, 16)
    assert inclusive_end_to_exclusive(None) is None


def test_window_is_half_open_on_both_sides():
    assert not overlaps_window(date(1990, 1, 1), date(1992, 10, 2))
    assert overlaps_window(date(1990, 1, 1), date(1992, 10, 3))
    assert not overlaps_window(date(1995, 1, 1), None)
    assert overlaps_window(date(1994, 12, 31), None)


def test_adjacent_intervals_are_accepted_and_overlap_is_refused():
    ensure_disjoint([(date(1991, 1, 1), date(1993, 1, 1), "a"), (date(1993, 1, 1), None, "b")])
    with pytest.raises(IngestionError) as error:
        ensure_disjoint([(date(1991, 1, 1), date(1993, 1, 2), "a"), (date(1993, 1, 1), None, "b")])
    assert error.value.code == "OVERLAPPING_INTERVALS"


def test_open_interval_followed_by_another_is_refused():
    with pytest.raises(IngestionError):
        ensure_disjoint([(date(1991, 1, 1), None, "open"), (date(1993, 1, 1), None, "later")])


def test_official_id_is_mandatory_and_must_match_the_document(tmp_path):
    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [])
        builder.add(
            "mandates",
            "9002",
            {
                "MandatoParlamentar": {
                    "Parlamentar": {"Codigo": "9999", "Mandatos": {"Mandato": [TERM_49_50]}}
                }
            },
        )

    plan, archive = build_plan(tmp_path, steps, ["9001", "9002"])
    assert [b.identity.senator_id for b in plan.senators] == ["9001"]
    assert ("OFFICIAL_SOURCE_DOCUMENT_MISSING", "9002") in reasons(plan)
    document = archive.find("detail", "9001")
    with pytest.raises(IngestionError, match="SENATOR_SOURCE_ID_MISMATCH"):
        normalize_identity(document, "9003")


def test_archived_file_must_match_its_recorded_hash(tmp_path):
    def steps(builder):
        builder.add("detail", "9001", {"DetalheParlamentar": {}}, corrupt_hash=True)
        builder.add("mandates", "9001", {})

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    assert plan.senators == []
    assert ("ARCHIVED_RESPONSE_HASH_MISMATCH", "9001") in reasons(plan)


def test_affiliation_end_is_exclusive_and_overlap_drops_only_affiliations(tmp_path):
    def steps(builder):
        builder.add_senator(
            "9001",
            [TERM_49_50],
            [
                affiliation("92", "PRN", "1991-02-01", "1994-02-20"),
                affiliation("22", "PFL", "1994-02-21"),
            ],
        )
        builder.add_senator(
            "9002",
            [TERM_49_50],
            [
                affiliation("92", "PRN", "1991-02-01", "1994-02-21"),
                affiliation("22", "PFL", "1994-02-21"),
            ],
            civil_name="Pessoa Ficticia Dois",
        )

    plan, _ = build_plan(tmp_path, steps, ["9001", "9002"])
    first, second = plan.senators
    assert [(a.abbreviation, a.ends_before) for a in first.affiliations] == [
        ("PRN", date(1994, 2, 21)),
        ("PFL", None),
    ]
    assert second.affiliations == [] and len(second.terms) == 1
    assert ("OVERLAPPING_INTERVALS", "9002") in reasons(plan)


def test_unidentified_party_and_year_only_claims_never_become_affiliations(tmp_path):
    def steps(builder):
        builder.add_senator(
            "9001",
            [TERM_49_50],
            [
                {"Partido": {"NomePartido": "Partido Sem Codigo"}},
                affiliation("92", "PRN", None, None, AnoFiliacao="1992", AnoDesfiliacao="1993"),
                affiliation("22", "PFL", "1993-01-01"),
            ],
        )

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    bundle = plan.senators[0]
    assert [a.abbreviation for a in bundle.affiliations] == ["PFL"]
    assert [c.party_abbreviation for c in bundle.year_only_claims] == ["PRN"]
    assert ("AFFILIATION_PARTY_NOT_IDENTIFIED", "9001") in reasons(plan)
    assert [p.abbreviation for p in plan.parties] == ["PFL"]


def test_party_missing_from_senate_catalog_is_not_invented(tmp_path):
    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [affiliation("777", "XYZ", "1993-01-01")])

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    assert plan.senators[0].affiliations == [] and plan.parties == []
    assert ("AFFILIATION_PARTY_NOT_IN_SENATE_CATALOG", "9001") in reasons(plan)


def test_no_party_interval_is_kept_without_creating_a_party(tmp_path):
    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [affiliation("163", "S/Partido", "1993-01-01")])

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    assert plan.senators[0].affiliations[0].is_without_party
    assert plan.parties == []


def test_reviewed_conflicts_stay_out_as_pending(tmp_path):
    def steps(builder):
        for senator_id in ("1537", "63", "1737"):
            builder.add_senator(
                senator_id,
                [TERM_49_50],
                [affiliation("22", "PFL", "1993-01-01")],
                civil_name=f"Pessoa {senator_id}",
            )

    plan, _ = build_plan(tmp_path, steps, ["1537", "63", "1737"])
    by_id = {b.identity.senator_id: b for b in plan.senators}
    assert "1537" not in by_id
    assert by_id["63"].affiliations == [] and len(by_id["63"].terms) == 1
    assert by_id["1737"].exercises == [] and len(by_id["1737"].affiliations) == 1
    codes = {
        item.senator_id for item in plan.pending if item.code == "WITHHELD_BY_DOCUMENTARY_REVIEW"
    }
    assert codes == {"1537", "63", "1737"}


def test_mandates_repeated_without_participation_collapse_and_alternates_need_exercise(tmp_path):
    repeated = mandate(
        None, ("49", "1991-02-01", "1995-01-31"), ("50", "1995-02-01", "1999-01-31"), role=None
    )
    alternate = mandate(
        "8",
        ("48", "1987-02-01", "1991-01-31"),
        ("49", "1991-02-01", "1995-01-31"),
        role="1º Suplente",
    )

    def steps(builder):
        builder.add_senator("9001", [TERM_49_50, repeated, alternate], [])

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    assert [(t.legislature_key, t.capacity) for t in plan.senators[0].terms] == [
        ("49-50", "holder")
    ]
    assert ("SUBSTITUTE_TERM_WITHOUT_EXERCISE", "9001") in reasons(plan)


def test_exercise_end_is_exclusive_and_participation_unknown_loads_no_exercise(tmp_path):
    exercise = [{"DataInicio": "1991-02-01", "DataFim": "1993-12-31"}]
    unknown = mandate(
        None,
        ("48", "1987-02-01", "1991-01-31"),
        ("49", "1991-02-01", "1995-01-31"),
        role=None,
        exercises=exercise,
    )
    holder = mandate(
        "7",
        ("49", "1991-02-01", "1995-01-31"),
        ("50", "1995-02-01", "1999-01-31"),
        exercises=exercise,
    )

    def steps(builder):
        builder.add_senator("9001", [holder], [])
        builder.add_senator("9002", [unknown], [], civil_name="Pessoa Ficticia Dois")

    plan, _ = build_plan(tmp_path, steps, ["9001", "9002"])
    first, second = plan.senators
    assert first.exercises[0].ends_before == date(1994, 1, 1)
    assert second.exercises == [] and second.terms[0].capacity is None
    assert ("TERM_PARTICIPATION_NOT_PUBLISHED", "9002") in reasons(plan)


def test_overlapping_or_out_of_term_exercises_are_refused(tmp_path):
    overlapping = [
        {"DataInicio": "1991-02-01", "DataFim": "1993-12-31"},
        {"DataInicio": "1993-06-01", "DataFim": "1994-06-30"},
    ]
    outside = [{"DataInicio": "1990-01-01", "DataFim": "1993-12-31"}]

    def steps(builder):
        builder.add_senator(
            "9001",
            [
                mandate(
                    "7",
                    ("49", "1991-02-01", "1995-01-31"),
                    ("50", "1995-02-01", "1999-01-31"),
                    exercises=overlapping,
                )
            ],
            [],
        )
        builder.add_senator(
            "9002",
            [
                mandate(
                    "7",
                    ("49", "1991-02-01", "1995-01-31"),
                    ("50", "1995-02-01", "1999-01-31"),
                    exercises=outside,
                )
            ],
            [],
            civil_name="Pessoa Dois",
        )

    plan, _ = build_plan(tmp_path, steps, ["9001", "9002"])
    assert all(bundle.exercises == [] for bundle in plan.senators)
    assert {"OVERLAPPING_INTERVALS", "EXERCISE_OUTSIDE_TERM"} <= {i.code for i in plan.pending}


def test_person_identity_is_derived_from_the_official_id_and_contact_data_is_dropped(tmp_path):
    assert person_id_for("123") == person_id_for("123") != person_id_for("124")

    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [])

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    stored = str(storable_payload(plan.senators[0].identity.document))
    assert "example.invalid" not in stored and "Pessoa Ficticia Um" in stored


def test_birth_date_is_required_to_create_an_identity(tmp_path):
    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [], birth=None)

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    assert plan.senators == []
    assert ("SENATOR_BIRTH_DATE_MISSING", "9001") in reasons(plan)


def test_homonymous_historical_parties_get_distinct_codes_and_labels(tmp_path):
    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [affiliation("22", "PFL", "1993-01-01")])

    plan, _ = build_plan(tmp_path, steps, ["9001"])
    party = plan.parties[0]
    assert party.code == "senado:party:22"
    assert qualified_abbreviation(party) == "PFL (1985-2007)"


def test_affiliation_document_with_other_senator_id_is_rejected(tmp_path):
    def steps(builder):
        builder.add_senator("9001", [TERM_49_50], [affiliation("22", "PFL", "1993-01-01")])

    _, archive = build_plan(tmp_path, steps, ["9001"])
    with pytest.raises(IngestionError, match="SENATOR_SOURCE_ID_MISMATCH"):
        normalize_affiliations(archive.find("affiliations", "9001"), "9002")


class RecordingConnection:
    """Stands in for psycopg: records how the transaction was opened and closed."""

    def __init__(self, status=0, autocommit=True):
        from types import SimpleNamespace

        self.autocommit = autocommit
        self.info = SimpleNamespace(transaction_status=status)
        self.opened_with = []
        self.closed_by = []

    def transaction(self, force_rollback=False):
        from contextlib import contextmanager

        @contextmanager
        def scope():
            self.opened_with.append(force_rollback)
            try:
                yield
            except BaseException:
                self.closed_by.append("rollback")
                raise
            self.closed_by.append("rollback" if force_rollback else "commit")

        return scope()


class ScriptedWriter:
    def __init__(self, passes, error=None):
        from collections import Counter
        from types import SimpleNamespace

        self.rows = [SimpleNamespace(inserted=Counter(p), conflicts=[]) for p in passes]
        self.error = error

    def write(self, plan):
        if self.error:
            raise self.error
        return self.rows.pop(0)


def test_dry_run_forces_rollback_even_when_every_pass_succeeds():
    from service.ingestion.historical_load import LoadMode, run_historical_load

    connection = RecordingConnection()
    run = run_historical_load(connection, ScriptedWriter([{"person": 3}, {}]), object())
    assert run.mode is LoadMode.DRY_RUN and not run.committed and run.idempotent
    assert connection.opened_with == [True] and connection.closed_by == ["rollback"]


def test_dry_run_rolls_back_when_the_writer_fails():
    from service.ingestion.historical_load import run_historical_load

    connection = RecordingConnection()
    with pytest.raises(RuntimeError):
        run_historical_load(connection, ScriptedWriter([], RuntimeError("boom")), object())
    assert connection.closed_by == ["rollback"]


def test_apply_commits_only_after_a_clean_idempotent_second_pass():
    from service.ingestion.historical_load import LoadMode, run_historical_load

    connection = RecordingConnection()
    run = run_historical_load(
        connection, ScriptedWriter([{"person": 3}, {}]), object(), LoadMode.APPLY
    )
    assert run.committed and connection.closed_by == ["commit"]


def test_apply_aborts_when_second_pass_inserts_or_rows_conflict():
    from service.ingestion.historical_load import LoadMode, run_historical_load

    connection = RecordingConnection()
    with pytest.raises(IngestionError, match="NOT_IDEMPOTENT"):
        run_historical_load(
            connection, ScriptedWriter([{"person": 3}, {"person": 1}]), object(), LoadMode.APPLY
        )
    assert connection.closed_by == ["rollback"]
    writer = ScriptedWriter([{"person": 3}, {}])
    writer.rows[0].conflicts = [{"table": "office_term"}]
    with pytest.raises(IngestionError, match="CONFLICT"):
        run_historical_load(RecordingConnection(), writer, object(), LoadMode.APPLY)


def test_runner_refuses_connections_where_rollback_would_only_be_a_savepoint():
    from service.ingestion.historical_load import run_historical_load

    for connection in (RecordingConnection(status=2), RecordingConnection(autocommit=False)):
        with pytest.raises(IngestionError, match="IDLE_AUTOCOMMIT"):
            run_historical_load(connection, ScriptedWriter([{}, {}]), object())
        assert connection.opened_with == []


def test_string_dry_run_mode_never_falls_through_to_apply():
    from service.ingestion.historical_load import run_historical_load

    connection = RecordingConnection()
    run = run_historical_load(connection, ScriptedWriter([{"person": 3}, {}]),
                              object(), "dry-run")
    assert not run.committed and connection.closed_by == ["rollback"]


@pytest.mark.parametrize("mode", [None, "", "unexpected"])
def test_invalid_load_mode_cannot_open_a_write_transaction(mode):
    from service.ingestion.historical_load import run_historical_load

    connection = RecordingConnection()
    with pytest.raises(ValueError):
        run_historical_load(connection, ScriptedWriter([{}, {}]), object(), mode)
    assert connection.opened_with == []


def test_conflicts_detected_only_on_second_pass_prevent_commit():
    from service.ingestion.historical_load import LoadMode, run_historical_load

    connection = RecordingConnection()
    writer = ScriptedWriter([{"person": 3}, {}])
    writer.rows[1].conflicts = [{"table": "office_term"}]
    with pytest.raises(IngestionError, match="CONFLICT"):
        run_historical_load(connection, writer, object(), LoadMode.APPLY)
    assert connection.closed_by == ["rollback"]
