"""XDG-compliant path resolution for sshtm data files."""

from __future__ import annotations

import os
from pathlib import Path


def _xdg_config_home() -> Path:
    """Return $XDG_CONFIG_HOME or its default (~/.config)."""
    env = os.environ.get("XDG_CONFIG_HOME")
    if env:
        return Path(env)
    return Path.home() / ".config"


def config_dir() -> Path:
    """Return the sshtm config directory, creating it if necessary."""
    path = _xdg_config_home() / "sshtm"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tunnels_file() -> Path:
    """Return the path to the tunnels TOML file."""
    return config_dir() / "tunnels.toml"


def history_file() -> Path:
    """Return the path to the history TOML file."""
    return config_dir() / "history.toml"


def sockets_dir() -> Path:
    """Return the directory for SSH ControlMaster sockets."""
    path = config_dir() / "sockets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pids_dir() -> Path:
    """Return the directory for SSH master PID files."""
    path = config_dir() / "pids"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    """Return the directory for per-master SSH log files."""
    path = config_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def socket_path_for(host: str) -> Path:
    """Return the ControlMaster socket path for *host*.

    Uses a short hash suffix to avoid collisions from host aliases.
    """
    import hashlib

    short_hash = hashlib.sha256(host.encode()).hexdigest()[:8]
    return sockets_dir() / f"{host}-{short_hash}.sock"


def pid_path_for(host: str) -> Path:
    """Return the PID file path for *host*'s master connection."""
    import hashlib

    short_hash = hashlib.sha256(host.encode()).hexdigest()[:8]
    return pids_dir() / f"{host}-{short_hash}.pid"


def log_path_for(host: str) -> Path:
    """Return the log file path for *host*'s master connection."""
    import hashlib

    short_hash = hashlib.sha256(host.encode()).hexdigest()[:8]
    return logs_dir() / f"{host}-{short_hash}.log"
