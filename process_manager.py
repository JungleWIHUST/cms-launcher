from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from config import AUTO_RESTART, LOG_DIR, MONITOR_INTERVAL, RESTART_DELAY, SERVICE_START_DELAY
from services import Service, SERVICE_MAP
from utils import ensure_directory, get_pid_path, kill_process, tail_file, terminate_process, wait_process


class ProcessManager:
    """Manage CMS service lifecycle and monitoring."""

    def __init__(self) -> None:
        self.services: dict[str, Service] = SERVICE_MAP
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._state: dict[str, dict[str, Any]] = {}

    def startup(self) -> None:
        """Create runtime directories and start all services."""
        ensure_directory(LOG_DIR)
        ensure_directory(Path(str(Path.home()) + "/.local/share/cms-launcher/pids"))
        self.start_all()

    def start_service(self, executable: str) -> Service | None:
        """Start a single service and return its runtime object."""
        service = self.services.get(executable)
        if service is None:
            return None
        if service.running:
            return service

        with self.lock:
            if service.running:
                return service
            service.mark_stopped()
            log_file = service.log_file
            log_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                process = subprocess.Popen(
                    [executable],
                    stdout=log_file.open("a", encoding="utf-8"),
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=os.environ.copy(),
                    start_new_session=True,
                    text=True,
                )
            except FileNotFoundError:
                service.mark_stopped()
                return None
            service.mark_started(process)
            self._write_pid(service)
            time.sleep(SERVICE_START_DELAY)
            return service

    def stop_service(self, executable: str, graceful: bool = True) -> Service | None:
        """Stop a single service."""
        service = self.services.get(executable)
        if service is None or service.process is None:
            return None
        pid = service.pid
        if pid is None:
            return None
        if graceful:
            terminate_process(pid)
            wait_process(pid, timeout=2.0)
        else:
            kill_process(pid)
        if service.process.poll() is None:
            os.kill(pid, signal.SIGKILL)
        service.mark_stopped()
        self._remove_pid(service)
        return service

    def restart_service(self, executable: str) -> Service | None:
        """Restart a single service."""
        self.stop_service(executable, graceful=True)
        time.sleep(RESTART_DELAY)
        return self.start_service(executable)

    def start_all(self) -> list[Service]:
        """Start all configured services."""
        started: list[Service] = []
        for executable in self.services:
            service = self.start_service(executable)
            if service is not None:
                started.append(service)
        return started

    def stop_all(self) -> list[Service]:
        """Stop all running services."""
        stopped: list[Service] = []
        for executable in list(self.services.keys()):
            service = self.stop_service(executable, graceful=True)
            if service is not None:
                stopped.append(service)
        return stopped

    def restart_all(self) -> list[Service]:
        """Restart all services."""
        self.stop_all()
        time.sleep(RESTART_DELAY)
        return self.start_all()

    def monitor_all(self) -> None:
        """Continuously monitor services and auto-restart crashed ones."""
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            for service in self.services.values():
                if service.process is None:
                    continue
                if service.process.poll() is not None:
                    code = service.process.returncode
                    service.mark_stopped()
                    self._state[service.executable] = {"status": "STOPPED", "exit_code": code}
                    if AUTO_RESTART and service.should_restart:
                        time.sleep(RESTART_DELAY)
                        self.start_service(service.executable)
            time.sleep(MONITOR_INTERVAL)

    def graceful_shutdown(self) -> None:
        """Stop every service and wait for them to exit."""
        self._stop_event.set()
        self.stop_all()

    def force_shutdown(self) -> None:
        """Force-stop every service."""
        self._stop_event.set()
        for service in self.services.values():
            if service.pid is not None:
                kill_process(service.pid)
        self.stop_all()

    def collect_statuses(self) -> list[dict[str, Any]]:
        """Collect a snapshot of service status information."""
        snapshots: list[dict[str, Any]] = []
        for service in self.services.values():
            snapshots.append(
                {
                    "name": service.display_name,
                    "executable": service.executable,
                    "pid": service.pid,
                    "status": "RUNNING" if service.running else "STOPPED",
                    "uptime": service.uptime,
                    "restart_count": service.restart_count,
                    "cpu": 0.0,
                    "ram": 0,
                    "logfile": str(service.log_file),
                }
            )
        return snapshots

    def _write_pid(self, service: Service) -> None:
        pid_path = get_pid_path(service.executable)
        if service.pid is not None:
            pid_path.write_text(str(service.pid), encoding="utf-8")

    def _remove_pid(self, service: Service) -> None:
        pid_path = get_pid_path(service.executable)
        pid_path.unlink(missing_ok=True)
