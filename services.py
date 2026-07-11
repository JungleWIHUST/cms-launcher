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
    log_file: Path = field(init=False)
    started_at: float | None = None
    restart_count: int = 0
    cpu_usage: float = 0.0
    ram_usage: int = 0
    status: str = "STOPPED"

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
    def pid(self) -> int | None:
        if self.process is None:
            return None
        return self.process.pid

    @property
    def running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    @property
    def exit_code(self) -> int | None:
        if self.process is None:
            return None
        return self.process.poll()

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
        self.started_at = time.time()
        self.status = "RUNNING"

    def mark_stopped(self) -> None:
        self.process = None
        self.started_at = None
        self.status = "STOPPED"

    def restarted(self) -> None:
        self.restart_count += 1


SERVICES: list[Service] = [Service(config) for config in SERVICE_DEFINITIONS]
SERVICE_MAP = {service.executable: service for service in SERVICES}
