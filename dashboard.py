from __future__ import annotations

import threading
import time
from typing import Any

from rich.console import Console
from rich.live import Live

from config import ADMIN_URL, CONTEST_URL
from process_manager import ProcessManager
from utils import colored_status, make_table


class Dashboard:
    """Render the launcher dashboard using Rich Live."""

    def __init__(self, manager: ProcessManager) -> None:
        self.manager = manager
        self.console = Console()
        self.live: Live | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the live dashboard loop."""
        self._stop_event.clear()
        self.live = Live(self._render(), console=self.console, refresh_per_second=4, transient=False)
        self.live.start()
        while not self._stop_event.is_set():
            self.live.update(self._render())
            time.sleep(0.25)
        self.live.stop()

    def stop(self) -> None:
        """Stop the dashboard loop."""
        self._stop_event.set()

    def _render(self) -> Any:
        rows: list[list[Any]] = []
        for item in self.manager.collect_statuses():
            rows.append(
                [
                    item["name"],
                    colored_status(str(item["status"])),
                    str(item.get("pid") or "-"),
                    f"{item['cpu']:.1f}%" if isinstance(item["cpu"], (int, float)) else str(item["cpu"]),
                    f"{item['ram']} B" if isinstance(item["ram"], int) else str(item["ram"]),
                    f"{item['uptime']:.0f}s" if isinstance(item["uptime"], (int, float)) else str(item["uptime"]),
                ]
            )
        table = make_table(["SERVICE", "STATUS", "PID", "CPU", "RAM", "UPTIME"], rows)
        return table
