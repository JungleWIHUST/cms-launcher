from __future__ import annotations


class Monitor:
    """Compatibility shim for the refactored manager-based architecture."""

    def __init__(self, manager: object) -> None:
        self.manager = manager

    def start(self) -> None:
        """Delegate monitoring startup to the process manager."""
        if hasattr(self.manager, "start_monitoring"):
            self.manager.start_monitoring()

    def stop(self) -> None:
        """No-op placeholder for compatibility."""
        return None

    def snapshot(self) -> list[dict[str, object]]:
        """Return dashboard data from the process manager."""
        if hasattr(self.manager, "collect_statuses"):
            return self.manager.collect_statuses()
        return []
