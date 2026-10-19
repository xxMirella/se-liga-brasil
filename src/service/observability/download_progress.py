"""Bounded terminal progress; redirected output keeps structured events."""

import sys
import time

from service.observability.reporting import EVENT_CONSUMER, emit_event

BAR_WIDTH = 20
REFRESH_SECONDS = 0.15


class DownloadProgress:
    def __init__(self, total_files: int, stream=None) -> None:
        self.stream = stream if stream is not None else sys.stderr
        self.total_files = total_files
        self.completed = 0
        self.failed = 0
        self.cached = 0
        self.resource_name = ""
        self.last_refresh = 0.0
        self.is_terminal = self.stream.isatty()

    def start_file(self, resource_name: str) -> None:
        clean_name = " ".join(resource_name.split())
        self.resource_name = "".join(char for char in clean_name if char.isprintable())[:60]
        emit_event(
            "download_started",
            resource_name=self.resource_name,
            total_files=self.total_files,
            completed=self.completed,
            remaining=self.total_files - self.completed - self.failed,
        )
        self.last_refresh = 0.0
        self.update_bytes(0, None)

    def update_bytes(self, received: int, expected: int | None) -> None:
        if not self.is_terminal:
            return
        now = time.monotonic()
        is_complete = expected is not None and received >= expected
        if now - self.last_refresh < REFRESH_SECONDS and not is_complete:
            return
        self.last_refresh = now
        if EVENT_CONSUMER.get() is not None:
            emit_event("download_bytes", received=received, expected=expected)
            return
        ratio = min(received / expected, 1.0) if expected else None
        filled = int(ratio * BAR_WIDTH) if ratio is not None else 0
        bar = "#" * filled + "-" * (BAR_WIDTH - filled)
        percentage = f"{ratio:.0%}" if ratio is not None else "tamanho desconhecido"
        remaining = self.total_files - self.completed - self.failed
        label = (
            f"[{bar}] {percentage} | {received / 1024**2:.1f} MiB | "
            f"{self.completed}/{self.total_files} concluídos | faltam {remaining} | "
            f"cache {self.cached} | falhas {self.failed} | {self.resource_name}"
        )
        self.stream.write(f"\r\033[2K{label}")
        self.stream.flush()

    def finish_file(self, succeeded: bool, cached: bool = False) -> None:
        self.completed += int(succeeded)
        self.failed += int(not succeeded)
        self.cached += int(succeeded and cached)
        emit_event(
            "download_progress",
            total_files=self.total_files,
            completed=self.completed,
            failed=self.failed,
            cached=self.cached,
            downloaded=self.completed - self.cached,
            remaining=self.total_files - self.completed - self.failed,
        )
