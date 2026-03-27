from __future__ import annotations

import subprocess
import time

from sshtm.config.paths import log_path_for, socket_path_for
from sshtm.core.health import check_master_alive, is_port_available, is_port_reachable
from sshtm.core.process import ProcessTracker
from sshtm.core.tunnel import Direction, Tunnel, TunnelStatus

_SSH_ERROR_HINTS: list[tuple[str, str]] = [
    ("Connection refused", "Host is unreachable or SSH is not running on the remote."),
    ("Connection timed out", "Host is unreachable. Check network/firewall."),
    ("Could not resolve hostname", "Hostname not found. Check spelling or DNS."),
    ("Permission denied", "Authentication failed. Check SSH key or credentials."),
    ("Host key verification failed", "Remote host key changed. Check ~/.ssh/known_hosts."),
    ("No route to host", "Network path unavailable. Check connectivity."),
    ("Address already in use", "Port is already bound by another process."),
    ("Connection reset by peer", "Remote side closed the connection unexpectedly."),
    ("Network is unreachable", "No network route. Check your connection."),
    ("Operation timed out", "SSH operation took too long. Host may be slow or unreachable."),
    ("Bad local forwarding specification", "Invalid port forwarding spec. Check ports."),
    ("remote port forwarding failed", "Remote could not bind the requested port."),
    ("administratively prohibited", "Server config forbids this forwarding type."),
]


def _read_ssh_log_tail(ssh_host: str, max_lines: int = 30) -> str:
    log_file = log_path_for(ssh_host)
    if not log_file.exists():
        return ""
    try:
        text = log_file.read_text(errors="replace")
        lines = text.strip().splitlines()
        return "\n".join(lines[-max_lines:])
    except OSError:
        return ""


def _enrich_error(base_msg: str, ssh_host: str, stderr: str = "") -> str:
    combined = f"{base_msg} {stderr} {_read_ssh_log_tail(ssh_host)}"
    hints: list[str] = []
    combined_lower = combined.lower()
    for pattern, hint in _SSH_ERROR_HINTS:
        if pattern.lower() in combined_lower:
            hints.append(hint)
    parts = [base_msg.strip()]
    if stderr.strip():
        parts.append(f"SSH: {stderr.strip()}")
    if hints:
        parts.append(f"Hint: {hints[0]}")
    return " | ".join(parts)


class TunnelManager:
    def __init__(self) -> None:
        self._tracker = ProcessTracker()

    def start_tunnel(self, tunnel: Tunnel) -> tuple[bool, str]:
        if tunnel.direction == Direction.LOCAL and not is_port_available(tunnel.local_port):
            return False, f"Local port {tunnel.local_port} is already in use"

        ok, master_msg = self._ensure_master(tunnel.ssh_host)
        if not ok:
            return False, master_msg

        success, msg = self._add_forward(tunnel)
        if not success:
            return False, msg

        if tunnel.direction == Direction.LOCAL:
            time.sleep(0.5)
            if not is_port_reachable(tunnel.local_port, timeout=3.0):
                pass

        return True, "Tunnel started"

    def stop_tunnel(self, tunnel: Tunnel) -> tuple[bool, str]:
        socket_path = socket_path_for(tunnel.ssh_host)
        if not socket_path.exists():
            return True, "No active master connection"

        success, msg = self._cancel_forward(tunnel)
        return success, msg

    def stop_all_for_host(self, ssh_host: str) -> tuple[bool, str]:
        socket_path = socket_path_for(ssh_host)
        if not socket_path.exists():
            return True, "No active master"

        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", f"ControlPath={socket_path}",
                    "-O", "exit",
                    ssh_host,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._tracker._cleanup_stale(ssh_host)
            return True, "Master connection closed"
        except subprocess.TimeoutExpired:
            self._tracker.kill_master(ssh_host)
            return True, "Master killed (timeout)"

    def check_tunnel_health(self, tunnel: Tunnel) -> TunnelStatus:
        socket_path = socket_path_for(tunnel.ssh_host)
        if not socket_path.exists():
            return TunnelStatus.STOPPED

        if not check_master_alive(str(socket_path), tunnel.ssh_host):
            self._tracker._cleanup_stale(tunnel.ssh_host)
            return TunnelStatus.ERROR

        if tunnel.direction == Direction.LOCAL:
            if is_port_reachable(tunnel.local_port, timeout=1.0):
                return TunnelStatus.RUNNING
            if not is_port_available(tunnel.local_port):
                return TunnelStatus.RUNNING
            return TunnelStatus.ERROR

        return TunnelStatus.RUNNING

    def change_ports(
        self,
        tunnel: Tunnel,
        new_local_port: int | None = None,
        new_remote_port: int | None = None,
    ) -> tuple[bool, str]:
        self._cancel_forward(tunnel)

        if new_local_port is not None:
            tunnel.local_port = new_local_port
        if new_remote_port is not None:
            tunnel.remote_port = new_remote_port

        return self._add_forward(tunnel)

    def _ensure_master(self, ssh_host: str) -> tuple[bool, str]:
        socket_path = socket_path_for(ssh_host)

        if socket_path.exists() and check_master_alive(str(socket_path), ssh_host):
            return True, "Master already running"

        self._tracker._cleanup_stale(ssh_host)
        log_path = log_path_for(ssh_host)

        cmd = [
            "ssh",
            "-f", "-N",
            "-o", "ControlMaster=yes",
            "-o", f"ControlPath={socket_path}",
            "-o", "ControlPersist=yes",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new",
            "-E", str(log_path),
            ssh_host,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            return False, _enrich_error(
                f"SSH connection to {ssh_host} timed out",
                ssh_host,
            )

        if result.returncode != 0:
            return False, _enrich_error(
                f"SSH master to {ssh_host} failed (exit {result.returncode})",
                ssh_host,
                result.stderr,
            )

        for _ in range(10):
            time.sleep(0.3)
            if socket_path.exists():
                break
        else:
            return False, _enrich_error(
                f"SSH master socket for {ssh_host} never appeared",
                ssh_host,
            )

        self._write_master_pid(ssh_host)
        return True, "Master started"

    def _write_master_pid(self, ssh_host: str) -> None:
        socket_path = socket_path_for(ssh_host)
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", f"ControlPath={socket_path}",
                    "-O", "check",
                    ssh_host,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # ssh -O check outputs: "Master running (pid=XXXX)"
            stderr = result.stderr
            if "pid=" in stderr:
                pid_str = stderr.split("pid=")[1].split(")")[0]
                self._tracker.write_pid(ssh_host, int(pid_str))
        except (subprocess.TimeoutExpired, ValueError, IndexError):
            pass

    def _add_forward(self, tunnel: Tunnel) -> tuple[bool, str]:
        socket_path = socket_path_for(tunnel.ssh_host)
        spec = tunnel.forward_spec()
        flag = tunnel.ssh_flag()

        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", f"ControlPath={socket_path}",
                    "-O", "forward",
                    flag, spec,
                    tunnel.ssh_host,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False, _enrich_error(
                    "Port forwarding failed",
                    tunnel.ssh_host,
                    result.stderr,
                )
            return True, "Forward added"
        except subprocess.TimeoutExpired:
            return False, _enrich_error(
                "Forward request timed out",
                tunnel.ssh_host,
            )

    def _cancel_forward(self, tunnel: Tunnel) -> tuple[bool, str]:
        socket_path = socket_path_for(tunnel.ssh_host)
        spec = tunnel.forward_spec()
        flag = tunnel.ssh_flag()

        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", f"ControlPath={socket_path}",
                    "-O", "cancel",
                    flag, spec,
                    tunnel.ssh_host,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False, _enrich_error(
                    "Cancel forwarding failed",
                    tunnel.ssh_host,
                    result.stderr,
                )
            return True, "Forward cancelled"
        except subprocess.TimeoutExpired:
            return False, _enrich_error(
                "Cancel request timed out",
                tunnel.ssh_host,
            )
