from __future__ import annotations

import os
import signal
import sys
import threading
import time
from typing import Any

from config import ADMIN_URL, CONTEST_URL, LOG_DIR, SERVICE_START_DELAY, TAIL_LINES
from dashboard import Dashboard
from logger import LauncherLogger
from monitor import Monitor
from process_manager import ProcessManager
from services import SERVICES
from utils import check_executable_exists, check_postgresql_running, check_tcp_port, clear_logs, detect_cms_conf, detect_cms_ranking_conf, detect_cms_venv, ensure_directory, format_duration, tail_file


class Launcher:
    """Entry point for the CMS launcher."""

    def __init__(self) -> None:
        self.logger = LauncherLogger()
        self.manager = ProcessManager()
        self.monitor = Monitor(self.manager)
        self.dashboard = Dashboard(self.monitor)
        self._shutdown_requested = False

    def run(self) -> None:
        """Run the launcher workflow."""
        self._print_banner()
        self._validate_environment()
        self._prepare_runtime()
        self.manager.start_all()
        self.monitor.start()
        self._start_dashboard()
        self._handle_commands()

    def _print_banner(self) -> None:
        self.logger.info("CMS Launcher starting")
        print("CMS Launcher")
        print("==============")

    def _validate_environment(self) -> None:
        venv = detect_cms_venv()
        if not venv.exists():
            self.logger.warning("CMS virtual environment not found at %s", venv)
        if detect_cms_conf() is None:
            self.logger.error("cms.conf not found")
        if detect_cms_ranking_conf() is None:
            self.logger.error("cms.ranking.conf not found")
        if not check_postgresql_running():
            self.logger.warning("PostgreSQL does not appear to be running")
        for service in SERVICES:
            if not check_executable_exists(service.executable):
                self.logger.warning("Executable %s was not found", service.executable)
        for port in (8888, 8889):
            if not check_tcp_port(port):
                self.logger.warning("Port %s is not listening", port)

    def _prepare_runtime(self) -> None:
        ensure_directory(LOG_DIR)
        clear_logs(LOG_DIR)

    def _start_dashboard(self) -> None:
        self.dashboard_thread = threading.Thread(target=self.dashboard.start, daemon=True)
        self.dashboard_thread.start()

    def _handle_commands(self) -> None:
        while not self._shutdown_requested:
            try:
                command = input("[cms-launcher] command> ").strip().lower()
            except KeyboardInterrupt:
                self._shutdown_requested = True
                break
            except EOFError:
                break
            if command in {"q", "quit"}:
                self._shutdown_requested = True
                break
            if command in {"r", "restart"}:
                self._restart_selected_service()
            elif command in {"s", "status"}:
                self._show_status()
            elif command in {"l", "logs"}:
                self._show_logs()
            elif command in {"t", "tail"}:
                self._tail_logs()
            elif command in {"h", "help"}:
                self._show_help()
            else:
                self.logger.warning("Unknown command: %s", command)
        self.shutdown()

    def _restart_selected_service(self) -> None:
        print("Available services:")
        for index, service in enumerate(SERVICES, start=1):
            print(f"{index}. {service.name} ({service.executable})")
        try:
            choice = int(input("Select service number: ").strip()) - 1
            if 0 <= choice < len(SERVICES):
                selected = SERVICES[choice]
                self.manager.restart_service(selected.executable)
                self.logger.info("Restarted %s", selected.executable)
        except (ValueError, KeyboardInterrupt):
            self.logger.warning("Invalid selection")

    def _show_status(self) -> None:
        for entry in self.manager.collect_statuses():
            print(f"{entry['name']}: {entry['status']} pid={entry['pid']} uptime={format_duration(entry['uptime'])}")

    def _show_logs(self) -> None:
        print("Recent launcher logs:")
        for line in tail_file(LOG_DIR / "launcher.log", TAIL_LINES):
            print(line.rstrip())

    def _tail_logs(self) -> None:
        print("Select service to tail:")
        for index, service in enumerate(SERVICES, start=1):
            print(f"{index}. {service.name} ({service.executable})")
        try:
            choice = int(input("Select service number: ").strip()) - 1
            if 0 <= choice < len(SERVICES):
                selected = SERVICES[choice]
                log_path = self.manager.services[selected.executable].log_file
                while True:
                    for line in tail_file(log_path, 20):
                        print(line.rstrip())
                    time.sleep(1)
        except KeyboardInterrupt:
            print("Stopped tailing")

    def _show_help(self) -> None:
        print("Commands: Q quit, R restart, S status, L logs, T tail, H help")

    def shutdown(self) -> None:
        """Gracefully stop services and exit."""
        self.logger.info("Shutting down launcher")
        self.dashboard.stop()
        self.monitor.stop()
        self.manager.graceful_shutdown()
        self.logger.info("Shutdown complete")


def main() -> None:
    try:
        Launcher().run()
    except KeyboardInterrupt:
        print("Interrupted")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Launcher error: {exc}")


if __name__ == "__main__":
    main()
