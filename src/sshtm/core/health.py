from __future__ import annotations

import socket
import subprocess


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def is_port_reachable(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            return True
    except (OSError, TimeoutError):
        return False


def check_master_alive(socket_path: str, ssh_host: str) -> bool:
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", f"ControlPath={socket_path}",
                "-O", "check",
                ssh_host,
            ],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
