"""Per-run private logs and optional terminal dashboard."""

import sys
from datetime import UTC, datetime
from threading import Event, RLock, Thread
from uuid import uuid4

from service.observability.completion import build_completion_lines
from service.observability.reporting import event_display, write_event
from service.observability.terminal_dashboard import TerminalDashboard
from storage.files import create_private_directory, write_json_line


class RunReporter:
    def __init__(self, storage_directory, stream=None) -> None:
        directory = storage_directory / "logs" / uuid4().hex
        create_private_directory(directory)
        self.log_path = directory / "rejections.ndjson"
        self.events_path = directory / "events.ndjson"
        self.rejected_files = set()
        explicit_stream = stream is not None
        stream = stream if explicit_stream else sys.stderr
        interactive = stream.isatty() and (explicit_stream or sys.stdout.isatty())
        self.dashboard = TerminalDashboard(stream) if interactive else None
        self.render_lock = RLock()
        self.stop_refresh = Event()
        self.refresh_thread = None
        self.completion = None
        self.stream = stream

    def __enter__(self):
        self.events = self.events_path.open("w", encoding="utf-8")
        self.rejections = self.log_path.open("w", encoding="utf-8")
        self.events_path.chmod(0o600)
        self.log_path.chmod(0o600)
        self.display = event_display(self.accept_event)
        self.display.__enter__()
        if self.dashboard:
            self.refresh_thread = Thread(target=self.refresh_dashboard, daemon=True)
            self.refresh_thread.start()
        return self

    def accept_event(self, event: dict) -> None:
        with self.render_lock:
            self.record_event(event)

    def refresh_dashboard(self) -> None:
        while not self.stop_refresh.wait(0.5):
            with self.render_lock:
                self.dashboard.render()

    def record_event(self, event: dict) -> None:
        event = {"timestamp": datetime.now(UTC).isoformat(), **event}
        if event["phase"] == "finished" and "artifacts" in event:
            self.completion = event
            self.stop_refresh.set()
        if event["phase"] != "download_bytes":
            write_json_line(self.events, event)
            self.events.flush()
        if event["phase"] in {"rejected", "resource_failed", "failed"}:
            if event.get("resource_id"):
                self.rejected_files.add(event["resource_id"])
            write_json_line(self.rejections, event)
            self.rejections.flush()
        if self.dashboard:
            self.dashboard.accept_event(event, len(self.rejected_files), self.log_path)
        elif event["phase"] != "download_bytes":
            write_event(event)

    def __exit__(self, exception_type, exception, trace):
        self.stop_refresh.set()
        if self.refresh_thread:
            self.refresh_thread.join(timeout=1)
        try:
            if self.dashboard:
                self.dashboard.render()
            if self.completion:
                self.stream.write("\n" + "\n".join(build_completion_lines(self.completion)) + "\n")
                self.stream.flush()
        finally:
            self.display.__exit__(exception_type, exception, trace)
            self.events.close()
            self.rejections.close()
