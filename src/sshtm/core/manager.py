from __future__ import annotations

import subprocess
import time
from pathlib import Path

from sshtm.config.paths import log_path_for, socket_path_for, pid_path_for
from sshtm.core.health import check_master_alive, is_port_available, is_port_reachable
from sshtm.core.process import ProcessTracker
from sshtm.core.tunnel import Direction, Tunnel, TunnelStatus


class TunnelManager:
    def __init__(self) -> None:
        self._tracker = ProcessTracker()

    def start_tunnel(self, tunnel: Tunnel) -> tuple[bool, str]:
        if tunnel.direction == Direction.LOCAL and not is_port_available(tunnel.local_port):
            return False, f"Local port {tunnel.local_port} is already in use"

        master_ok = self._ensure_master(tunnel.ssh_host)
        if not master_ok:
            return False, f"Failed to establish SSH master to {tunnel.ssh_host}"

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

    def _ensure_master(self, ssh_host: str) -> bool:
        socket_path = socket_path_for(ssh_host)

        if socket_path.exists() and check_master_alive(str(socket_path), ssh_host):
            return True

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
            return False

        if result.returncode != 0:
            return False

        for _ in range(10):
            time.sleep(0.3)
            if socket_path.exists():
                break
        else:
            return False

        self._write_master_pid(ssh_host)
        return True

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
                return False, f"Forward failed: {result.stderr.strip()}"
            return True, "Forward added"
        except subprocess.TimeoutExpired:
            return False, "Forward request timed out"

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
                return False, f"Cancel failed: {result.stderr.strip()}"
            return True, "Forward cancelled"
        except subprocess.TimeoutExpired:
            return False, "Cancel request timed out"
