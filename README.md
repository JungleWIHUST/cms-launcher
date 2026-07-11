# CMS Launcher

A lightweight terminal launcher for a single-machine CMS installation.

## Features

- Starts and monitors the core CMS services
- Supports graceful stop, restart, and auto-restart
- Writes separate logs for the launcher and each CMS service
- Provides a Rich-based dashboard and keyboard-driven commands

## Requirements

- Python 3.11+
- rich
- psutil

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the launcher:

```bash
python launcher.py
```

## Keyboard Commands

- Q: Quit and stop all services
- R: Restart a selected service
- S: Show service status
- L: Show recent launcher logs
- T: Tail a service log
- H: Show help

## Configuration

Configuration is centralized in [config.py](config.py).

You can override the CMS environment paths with:

- CMS_VENV
- CMS_LOG_DIR
- CMS_RUNTIME_DIR
- CMS_CONFIG_DIR

## Directory Structure

- logs/: CMS service logs and launcher log
- pids/: PID files for services

## Troubleshooting

- Ensure the CMS virtual environment exists and contains the CMS executables.
- Ensure PostgreSQL is running.
- Check the launcher log in logs/launcher.log.
