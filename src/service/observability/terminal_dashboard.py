"""A single terminal panel, refreshed in place without scrolling event lines."""

import shutil
import time
from collections import deque

STAGE_NAMES = {
    "start": "Iniciando",
    "discovery": "Arquivos encontrados",
    "download_started": "Download",
    "download_bytes": "Download",
    "download_progress": "Download",
    "download": "Download",
    "validate_started": "Validação",
    "validate": "Validação",
    "validate_progress": "Validação",
    "ingest_started": "Ingestão",
    "ingest": "Ingestão",
    "ingest_progress": "Ingestão",
    "profiles_refresh_started": "Atualização dos perfis",
    "profiles_refresh_finished": "Perfis atualizados",
    "finished": "Finalizado",
    "failed": "Falha",
}


class TerminalDashboard:
    def __init__(self, stream) -> None:
        self.stream = stream
        self.state = {}
        self.notices = deque(maxlen=3)
        self.drawn_lines = 0
        self.last_draw = 0.0
        self.started_at = time.monotonic()
        self.last_activity = self.started_at

    def accept_event(self, event: dict, rejected_files: int, log_path) -> None:
        self.last_activity = time.monotonic()
        self.state.update({key: value for key, value in event.items() if key != "phase"})
        if event["phase"] in STAGE_NAMES:
            self.state["stage"] = STAGE_NAMES[event["phase"]]
        if event["phase"] == "ingest_started":
            self.state.update(processed_records=0, total_records=event.get("total_records", "?"))
        if event["phase"] == "validate_started":
            self.state["rows_scanned"] = 0
        if event["phase"] in {"rejected", "resource_failed", "failed"}:
            location = event.get("entry_name") or event.get("resource_name") or "operação"
            candidate = event.get("context", {}).get("candidate_name", "")
            self.notices.append(
                f"{location}:{event.get('row_number', '-')} — {candidate} — {event['message']}"
            )
        self.state["rejected_files"] = rejected_files
        self.state["log_path"] = str(log_path)
        if time.monotonic() - self.last_draw >= 0.15 or event["phase"] == "finished":
            self.render()

    def build_lines(self) -> list[str]:
        state = self.state
        received, expected = state.get("received", 0), state.get("expected")
        ratio = min(received / expected, 1.0) if expected else None
        filled = int(ratio * 20) if ratio is not None else 0
        bar = "#" * filled + "-" * (20 - filled)
        percent = f"{ratio:.0%}" if ratio is not None else "tamanho desconhecido"
        return [
            "SE LIGA, BRASIL — CRAWLER TSE",
            f"Etapa: {state.get('stage', 'Preparando')} | {state.get('resource_name', '')}"
            f" | {state.get('status', '')}",
            f"Encontrados: {state.get('total_files', 0)} | Concluídos: {state.get('completed', 0)}"
            f" | Restantes: {state.get('remaining', 0)} | Cache: {state.get('cached', 0)}",
            self.build_activity_line(bar, percent, received),
            f"Arquivos com rejeições/falhas: {state.get('rejected_files', 0)}",
            f"Log de motivos: {state.get('log_path', '')}",
            *[f"Aviso: {notice}" for notice in self.notices],
            *[""] * (3 - len(self.notices)),
        ]

    def build_activity_line(self, bar, percent, received) -> str:
        elapsed = int(time.monotonic() - self.started_at)
        waiting = int(time.monotonic() - self.last_activity)
        stage = self.state.get("stage", "")
        if stage == "Ingestão":
            detail = (
                f"Registros: {self.state.get('processed_records', 0)}/"
                f"{self.state.get('total_records', '?')}"
            )
        elif stage == "Validação":
            detail = f"Linhas examinadas: {self.state.get('rows_scanned', 0)}"
        elif stage == "Download":
            detail = f"Download [{bar}] {percent} | {received / 1024**2:.1f} MiB"
        else:
            detail = self.state.get("status", "Operação em andamento")
        return f"{detail} | Tempo: {elapsed}s | Desde o último avanço: {waiting}s"

    def render(self) -> None:
        width = max(20, shutil.get_terminal_size(fallback=(100, 24)).columns - 1)
        if self.drawn_lines:
            self.stream.write(f"\033[{self.drawn_lines}A")
        lines = self.build_lines()
        for line in lines:
            safe_line = "".join(char for char in line if char.isprintable())[:width]
            self.stream.write(f"\r\033[2K{safe_line}\n")
        self.stream.flush()
        self.drawn_lines = len(lines)
        self.last_draw = time.monotonic()
