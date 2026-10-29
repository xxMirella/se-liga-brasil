"""Run a historical load as a dry run (always rolled back) or as one committed transaction.

The runner is source-agnostic: a writer receives a plan inside an open transaction and reports
what it inserted. The same plan is written twice in the same transaction, and the second pass
must insert nothing; that is the idempotency proof, in dry run and before every commit.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from psycopg.pq import TransactionStatus

from service.ingestion.contracts import IngestionError


class LoadMode(StrEnum):
    DRY_RUN = "dry-run"
    APPLY = "apply"


@dataclass
class LoadRun:
    mode: LoadMode
    first_pass: object
    second_pass: object
    committed: bool

    @property
    def idempotent(self) -> bool:
        return sum(self.second_pass.inserted.values()) == 0


def run_historical_load(
    connection,
    writer,
    plan,
    mode: LoadMode = LoadMode.DRY_RUN,
    after_commit: Callable[[object], None] | None = None,
) -> LoadRun:
    """Dry run is the default and cannot commit: rollback is forced, including on any error."""
    mode = LoadMode(mode)
    _require_top_level_transaction_scope(connection)
    if mode is LoadMode.DRY_RUN:
        return _dry_run(connection, writer, plan)
    run = _apply(connection, writer, plan)
    if after_commit:
        after_commit(connection)
    return run


def _require_top_level_transaction_scope(connection) -> None:
    """With autocommit and no open transaction, transaction() is a real BEGIN, not a savepoint."""
    idle = connection.info.transaction_status == TransactionStatus.IDLE
    if not connection.autocommit or not idle:
        raise IngestionError("HISTORICAL_LOAD_REQUIRES_IDLE_AUTOCOMMIT_CONNECTION")


def _dry_run(connection, writer, plan) -> LoadRun:
    with connection.transaction(force_rollback=True):
        first = writer.write(plan)
        second = writer.write(plan)
    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise IngestionError("DRY_RUN_LEFT_TRANSACTION_OPEN")
    return LoadRun(LoadMode.DRY_RUN, first, second, committed=False)


def _apply(connection, writer, plan) -> LoadRun:
    with connection.transaction():
        first = writer.write(plan)
        if first.conflicts:
            raise IngestionError(
                "EXISTING_ROWS_CONFLICT_WITH_LOAD", {"count": len(first.conflicts)}
            )
        second = writer.write(plan)
        if second.conflicts:
            raise IngestionError(
                "EXISTING_ROWS_CONFLICT_WITH_LOAD", {"count": len(second.conflicts)}
            )
        if sum(second.inserted.values()):
            raise IngestionError("HISTORICAL_LOAD_NOT_IDEMPOTENT", dict(second.inserted))
    return LoadRun(LoadMode.APPLY, first, second, committed=True)
