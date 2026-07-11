from __future__ import annotations

import threading
import time
from typing import Any

from config import MONITOR_INTERVAL
from process_manager import ProcessManager
from utils import cpu_usage, format_duration, format_bytes, ram_usage


class Monitor:
    """Background monitor that refreshes service metrics."""

    def __init__(self, manager: ProcessManager) -> None:
        self.manager = manager
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._latest: list[dict[str, Any]] = []

    def start(self) -> None:
        """Start the monitor loop in the background."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitor loop."""
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._refresh()
            time.sleep(MONITOR_INTERVAL)

    def _refresh(self) -> None:
        snapshots: list[dict[str, Any]] = []
        for service in self.manager.services.values():
            pid = service.pid
            snapshots.append(
                {
                    "name": service.display_name,
                    "executable": service.executable,
                    "pid": pid,
                    "status": "RUNNING" if service.running else "STOPPED",
                    "uptime": format_duration(service.uptime),
                    "restart_count": service.restart_count,
                    "cpu": f"{cpu_usage(pid):.1f}%",
                    "ram": format_bytes(ram_usage(pid)),
                    "logfile": str(service.log_file),
                }
            )
        self._latest = snapshots

    def snapshot(self) -> list[dict[str, Any]]:
        """Return the latest metrics snapshot."""
        return list(self._latest)
