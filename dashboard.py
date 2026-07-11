from __future__ import annotations

import threading
import time
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.table import Table

from config import ADMIN_URL, CONTEST_URL
from monitor import Monitor
from utils import colored_status, make_panel, make_table


class Dashboard:
    """Render the launcher dashboard using Rich Live."""

    def __init__(self, monitor: Monitor) -> None:
        self.monitor = monitor
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
        rows = []
        for item in self.monitor.snapshot():
            rows.append(
                [
                    item["name"],
                    colored_status(item["status"]),
                    str(item.get("pid") or "-"),
                    item["cpu"],
                    item["ram"],
                    item["uptime"],
                ]
            )
        table = make_table(["SERVICE", "STATUS", "PID", "CPU", "RAM", "UPTIME"], rows)
        footer = (
            "Admin\n"
            f"{ADMIN_URL}\n\n"
            "Contest\n"
            f"{CONTEST_URL}\n\n"
            "Commands\n"
            "Q Quit\n"
            "R Restart\n"
            "S Status\n"
            "L Logs\n"
            "T Tail"
        )
        return table
