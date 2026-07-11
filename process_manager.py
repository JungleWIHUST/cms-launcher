from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

import psutil

from config import AUTO_RESTART, CMS_BIN, LOG_DIR, MONITOR_INTERVAL, PID_DIR, RESTART_DELAY, SERVICE_START_DELAY
from logger import LauncherLogger
from services import Service, SERVICE_MAP
from utils import ensure_directory, get_pid_path, kill_process, terminate_process, wait_process


class ProcessManager:
    """Own the full lifecycle of CMS services, including monitoring and auto-restart."""

    def __init__(self, logger: LauncherLogger | None = None) -> None:
        self.services: dict[str, Service] = SERVICE_MAP
        self.lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self.logger = logger
        self._last_started: dict[str, float] = {}

    def startup(self) -> None:
        """Create runtime directories and start all services."""
        ensure_directory(LOG_DIR)
        ensure_directory(PID_DIR)
        self.start_all()

    def start_service(self, executable: str) -> Service | None:
        """Start a single service using the CMS virtual environment binary path."""
        service = self.services.get(executable)
        if service is None:
            return None

        with self.lock:
            if service.running:
                return service

            service_path = CMS_BIN / executable
            if not service_path.exists():
                message = f"[FAILED] {service.display_name}\nExecutable not found:\n{service_path}"
                print(message)
                self._log_service_failure(service, message)
                service.mark_failed(message)
                return service

            try:
                log_handle = service.log_file.open("a", encoding="utf-8")
            except OSError as exc:
                message = f"[FAILED] {service.display_name}\nUnable to open log file:\n{exc}"
                print(message)
                self._log_service_failure(service, message)
                service.mark_failed(message)
                return service

            try:
                process = subprocess.Popen(
                    [str(service_path)],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=os.environ.copy(),
                    start_new_session=True,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                log_handle.close()
                message = f"[FAILED] {service.display_name}\nFailed to launch process:\n{exc}"
                print(message)
                self._log_service_failure(service, message)
                service.mark_failed(message)
                return service

            service.mark_started(process)
            self._write_pid(service)
            print(f"[ OK ] {service.display_name}")
            time.sleep(SERVICE_START_DELAY)

            if process.poll() is not None:
                code = process.returncode
                service.mark_stopped(exit_code=code)
                self._remove_pid(service)
                message = (
                    f"{service.executable} exited immediately\n"
                    f"Exit code: {code}\n"
                    f"See {service.log_file}"
                )
                print(message)
                self._log_service_failure(service, message, exit_code=code)
                return service

            self._last_started[executable] = time.time()
            self._log_service_event(service, "started")
            return service

    def stop_service(self, executable: str, graceful: bool = True) -> Service | None:
        """Stop a single service gracefully or forcefully."""
        service = self.services.get(executable)
        if service is None:
            return None

        with self.lock:
            if service.pid is None and service.process is None:
                return None

            pid = service.pid
            if pid is None:
                return None

            if graceful:
                terminate_process(pid)
                if not wait_process(pid, timeout=3.0):
                    kill_process(pid)
            else:
                kill_process(pid)

            exit_code = None
            if service.process is not None:
                exit_code = service.process.poll()
                if exit_code is None:
                    try:
                        service.process.wait(timeout=2.0)
                        exit_code = service.process.returncode
                    except subprocess.TimeoutExpired:
                        if service.process.poll() is None:
                            service.process.kill()
                            service.process.wait(timeout=2.0)
                            exit_code = service.process.returncode

            service.mark_stopped(exit_code=exit_code)
            self._remove_pid(service)
            self._log_service_event(service, "stopped")
            return service

    def restart_service(self, executable: str) -> Service | None:
        """Restart a single service after a brief delay."""
        with self.lock:
            self.stop_service(executable, graceful=True)
            time.sleep(RESTART_DELAY)
            return self.start_service(executable)

    def start_all(self) -> list[Service]:
        """Start every configured service and report the outcome."""
        started: list[Service] = []
        for executable in self.services:
            service = self.start_service(executable)
            if service is not None:
                started.append(service)
        return started

    def stop_all(self) -> list[Service]:
        """Stop every managed service."""
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

    def start_monitoring(self) -> None:
        """Launch the monitoring thread."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            with self.lock:
                for service in self.services.values():
                    if service.process is None:
                        continue
                    code = service.process.poll()
                    if code is None:
                        self._refresh_process_metrics(service)
                        continue
                    service.mark_stopped(exit_code=code)
                    self._remove_pid(service)
                    self._log_service_failure(service, f"{service.executable} crashed", exit_code=code)
                    print(f"{service.executable} crashed")
                    print("Restarting...")
                    if AUTO_RESTART and service.should_restart and not self._stop_event.is_set():
                        service.restarted()
                        time.sleep(RESTART_DELAY)
                        self.start_service(service.executable)
            time.sleep(MONITOR_INTERVAL)

    def graceful_shutdown(self) -> None:
        """Stop every service gracefully, then forcefully if needed."""
        self._stop_event.set()
        for executable in list(self.services.keys()):
            self._terminate_process_tree(executable)
        self.stop_all()

    def force_shutdown(self) -> None:
        """Force-stop every service immediately."""
        self._stop_event.set()
        for executable in list(self.services.keys()):
            service = self.services[executable]
            if service.pid is not None:
                kill_process(service.pid)
        self.stop_all()

    def collect_statuses(self) -> list[dict[str, Any]]:
        """Collect a snapshot of service runtime metrics."""
        snapshots: list[dict[str, Any]] = []
        with self.lock:
            for service in self.services.values():
                if service.pid is not None and service.status == "RUNNING":
                    self._refresh_process_metrics(service)
                snapshots.append(
                    {
                        "name": service.display_name,
                        "executable": service.executable,
                        "status": service.status,
                        "pid": service.pid,
                        "cpu": round(service.cpu_usage, 1),
                        "ram": service.ram_usage,
                        "uptime": service.uptime,
                        "restart_count": service.restart_count,
                        "exit_code": service.exit_code,
                    }
                )
        return snapshots

    def _terminate_process_tree(self, executable: str) -> None:
        service = self.services.get(executable)
        if service is None or service.pid is None:
            return
        try:
            parent = psutil.Process(service.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            _, alive = psutil.wait_procs([parent, *parent.children(recursive=True)], timeout=3)
            for proc in alive:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return

    def _refresh_process_metrics(self, service: Service) -> None:
        if service.pid is None:
            service.cpu_usage = 0.0
            service.ram_usage = 0
            return
        try:
            process = psutil.Process(service.pid)
            service.cpu_usage = process.cpu_percent(interval=None)
            service.ram_usage = process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            if service.cpu_usage == 0.0 and service.ram_usage == 0:
                service.cpu_usage = 0.0
                service.ram_usage = 0
            else:
                service.cpu_usage = service.cpu_usage
                service.ram_usage = service.ram_usage

    def _write_pid(self, service: Service) -> None:
        pid_path = get_pid_path(service.executable)
        if service.pid is not None:
            pid_path.write_text(str(service.pid), encoding="utf-8")

    def _remove_pid(self, service: Service) -> None:
        pid_path = get_pid_path(service.executable)
        pid_path.unlink(missing_ok=True)

    def _log_service_event(self, service: Service, event: str) -> None:
        if self.logger is not None:
            self.logger.info("%s %s", service.executable, event)

    def _log_service_failure(self, service: Service, message: str, exit_code: int | None = None) -> None:
        if self.logger is not None:
            self.logger.error("%s failed: %s", service.executable, message)
        with (LOG_DIR / "launcher.log").open("a", encoding="utf-8") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {service.executable} failed")
            if exit_code is not None:
                handle.write(f" (exit_code={exit_code})")
            handle.write(f": {message}\n")
