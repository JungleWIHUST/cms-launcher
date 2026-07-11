from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True, frozen=True)
class ServiceConfig:
    """Static configuration for a single CMS service."""

    name: str
    executable: str
    enabled: bool = True
    auto_restart: bool = True


HOME = Path.home()

CMS_VENV = Path(os.environ.get("CMS_VENV", str(HOME / "cms_venv")))
CMS_BIN = CMS_VENV / ("Scripts" if os.name == "nt" else "bin")

LOG_DIR = Path(os.environ.get("CMS_LOG_DIR", str(HOME / ".local" / "share" / "cms-launcher" / "logs")))
RUNTIME_DIR = Path(os.environ.get("CMS_RUNTIME_DIR", str(HOME / ".local" / "share" / "cms-launcher")))
PID_DIR = RUNTIME_DIR / "pids"
CONFIG_DIR = Path(os.environ.get("CMS_CONFIG_DIR", "/usr/local/etc"))

CMS_CONFIG = CONFIG_DIR / "cms.conf"
CMS_RANKING_CONFIG = CONFIG_DIR / "cms.ranking.conf"

ADMIN_URL = "http://localhost:8889"
CONTEST_URL = "http://localhost:8888"

AUTO_RESTART = True
RESTART_DELAY = 3.0
MONITOR_INTERVAL = 1.0
SERVICE_START_DELAY = 1.0
LOG_HISTORY_LINES = 300
TAIL_LINES = 50
DEFAULT_PORTS = (8888, 8889)

ENV = os.environ.copy()
PATH_VALUE = ENV.get("PATH", "")
if str(CMS_BIN) not in PATH_VALUE.split(os.pathsep):
    ENV["PATH"] = f"{CMS_BIN}{os.pathsep}{PATH_VALUE}" if PATH_VALUE else str(CMS_BIN)

SERVICE_DEFINITIONS: list[ServiceConfig] = [
    ServiceConfig(name="Log Service", executable="cmsLogService"),
    ServiceConfig(name="Resource Service", executable="cmsResourceService"),
    ServiceConfig(name="Scoring Service", executable="cmsScoringService"),
    ServiceConfig(name="Checker", executable="cmsChecker"),
    ServiceConfig(name="Evaluation Service", executable="cmsEvaluationService"),
    ServiceConfig(name="Worker", executable="cmsWorker"),
    ServiceConfig(name="Contest Web Server", executable="cmsContestWebServer"),
    ServiceConfig(name="Admin Web Server", executable="cmsAdminWebServer"),
    ServiceConfig(name="Ranking Web Server", executable="cmsRankingWebServer"),
    ServiceConfig(name="Printing Service", executable="cmsPrintingService"),
]
