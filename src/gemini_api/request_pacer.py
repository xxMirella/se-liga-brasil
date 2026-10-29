"""Spaces API calls and caps how many calls one run may spend (free-tier quotas are small)."""

import time
from collections.abc import Callable


class CallBudgetExhaustedError(RuntimeError):
    """The run reached its own call budget; rerun later, cached answers are kept."""


class RequestPacer:
    def __init__(
        self,
        min_interval_seconds: float,
        max_calls: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._min_interval_seconds = min_interval_seconds
        self._max_calls = max_calls
        self._clock = clock
        self._sleep = sleep
        self._last_call_at: float | None = None
        self.calls_made = 0

    def wait_turn(self) -> None:
        if self.calls_made >= self._max_calls:
            raise CallBudgetExhaustedError("GEMINI_CALL_BUDGET_EXHAUSTED")
        if self._last_call_at is not None:
            remaining = self._min_interval_seconds - (self._clock() - self._last_call_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_call_at = self._clock()
        self.calls_made += 1
