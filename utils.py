from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import CMS_BIN, CMS_CONFIG, CMS_RANKING_CONFIG, CMS_VENV, LOG_DIR, PID_DIR, TAIL_LINES, ENV


CONSOLE = Console()


def ensure_directory(path: str | os.PathLike[str]) -> Path:
    """Create a directory and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def clear_logs(log_dir: str | os.PathLike[str] | None = None) -> None:
    """Remove existing log files in the target directory."""
    target = Path(log_dir or LOG_DIR)
    if target.exists():
        for file_path in target.glob("*.log"):
            file_path.unlink(missing_ok=True)


def tail_file(path: str | os.PathLike[str], lines: int = TAIL_LINES) -> list[str]:
    """Read the last N lines from a file if it exists."""
    candidate = Path(path)
    if not candidate.exists():
        return []
    with candidate.open("r", encoding="utf-8", errors="ignore") as handle:
        return handle.readlines()[-lines:]


def format_bytes(value: int | float) -> str:
    """Format bytes into a human readable string."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    if seconds <= 0:
        return "00:00:00"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_timestamp(timestamp: float | None) -> str:
    """Format a Unix timestamp into a readable string."""
    if not timestamp:
        return "n/a"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def detect_cms_venv() -> Path:
    """Locate a CMS virtual environment."""
    candidates = [CMS_VENV, Path(os.environ.get("CMS_VENV", ""))]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return CMS_VENV


def detect_executable(executable: str) -> Path | None:
    """Locate an executable in the configured CMS virtual environment."""
    path = CMS_BIN / executable
    if path.exists():
        return path
    return None


def detect_cms_conf() -> Path | None:
    """Locate cms.conf."""
    return CMS_CONFIG if CMS_CONFIG.exists() else None


def detect_cms_ranking_conf() -> Path | None:
    """Locate cms.ranking.conf."""
    return CMS_RANKING_CONFIG if CMS_RANKING_CONFIG.exists() else None


def check_postgresql_running() -> bool:
    """Check whether a PostgreSQL server appears to be available."""
    try:
        result = subprocess.run(["pg_isready"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_executable_exists(executable: str) -> bool:
    """Check whether a command is available."""
    return detect_executable(executable) is not None


def check_tcp_port(port: int) -> bool:
    """Check whether a TCP port is currently listening on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def process_exists(pid: int) -> bool:
    """Return whether a process with the PID exists."""
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def terminate_process(pid: int) -> bool:
    """Gracefully terminate a process."""
    try:
        process = psutil.Process(pid)
        process.terminate()
        return True
    except Exception:
        return False


def kill_process(pid: int) -> bool:
    """Forcefully kill a process."""
    try:
        process = psutil.Process(pid)
        process.kill()
        return True
    except Exception:
        return False


def wait_process(pid: int, timeout: float = 5.0) -> bool:
    """Wait for a process to exit within the timeout."""
    try:
        process = psutil.Process(pid)
        process.wait(timeout=timeout)
        return True
    except Exception:
        return False


def cpu_usage(pid: int | None) -> float:
    """Return CPU percent for a process if available."""
    if pid is None:
        return 0.0
    try:
        process = psutil.Process(pid)
        return process.cpu_percent(interval=None)
    except Exception:
        return 0.0


def ram_usage(pid: int | None) -> int:
    """Return RSS memory in bytes for a process if available."""
    if pid is None:
        return 0
    try:
        process = psutil.Process(pid)
        return process.memory_info().rss
    except Exception:
        return 0


def colored_status(status: str) -> str:
    """Return a colorized status string for the terminal."""
    mapping = {
        "RUNNING": "[green]RUNNING[/green]",
        "STOPPED": "[red]STOPPED[/red]",
        "STARTING": "[yellow]STARTING[/yellow]",
        "FAILED": "[red]FAILED[/red]",
        "RESTARTING": "[magenta]RESTARTING[/magenta]",
    }
    return mapping.get(status, status)


def make_table(headers: list[str], rows: list[list[Any]]) -> Table:
    """Create a Rich table."""
    table = Table(show_header=True, header_style="bold cyan")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*[str(item) for item in row])
    return table


def make_panel(title: str, content: str) -> Panel:
    """Create a Rich panel."""
    return Panel.fit(content, title=title, border_style="cyan")


def make_banner(title: str) -> str:
    """Create a CLI banner string."""
    return f"\n=== {title} ===\n"


def get_pid_path(service_name: str) -> Path:
    """Return the PID file path for a service."""
    ensure_directory(PID_DIR)
    return PID_DIR / f"{service_name}.pid"
