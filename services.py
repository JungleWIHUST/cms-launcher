from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import time

from config import LOG_DIR, ServiceConfig, SERVICE_DEFINITIONS


@dataclass
class Service:
    """Runtime state for a managed CMS service."""

    config: ServiceConfig
    process: subprocess.Popen | None = None
    pid: int | None = None
    log_file: Path = field(init=False)
    started_at: float | None = None
    restart_count: int = 0
    cpu_usage: float = 0.0
    ram_usage: int = 0
    status: str = "STOPPED"
    exit_code: int | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        self.log_file = LOG_DIR / f"{self.config.executable}.log"

    @property
    def executable(self) -> str:
        return self.config.executable

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def display_name(self) -> str:
        return self.config.name

    @property
    def running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    @property
    def uptime(self) -> float:
        if self.started_at is None:
            return 0.0
        return time.time() - self.started_at

    @property
    def should_restart(self) -> bool:
        return self.config.auto_restart

    def mark_started(self, process: subprocess.Popen) -> None:
        self.process = process
        self.pid = process.pid
        self.started_at = time.time()
        self.status = "RUNNING"
        self.exit_code = None
        self.last_error = None

    def mark_stopped(self, exit_code: int | None = None) -> None:
        self.process = None
        self.started_at = None
        self.pid = None
        self.status = "STOPPED"
        self.exit_code = exit_code

    def mark_failed(self, reason: str, exit_code: int | None = None) -> None:
        self.process = None
        self.started_at = None
        self.pid = None
        self.status = "FAILED"
        self.exit_code = exit_code
        self.last_error = reason

    def restarted(self) -> None:
        self.restart_count += 1


SERVICES: list[Service] = [Service(config) for config in SERVICE_DEFINITIONS]
SERVICE_MAP = {service.executable: service for service in SERVICES}
