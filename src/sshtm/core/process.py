from __future__ import annotations

import os
import signal
from pathlib import Path

from sshtm.config.paths import pid_path_for, socket_path_for


class ProcessTracker:
    def write_pid(self, host: str, pid: int) -> None:
        path = pid_path_for(host)
        path.write_text(str(pid))

    def read_pid(self, host: str) -> int | None:
        path = pid_path_for(host)
        if not path.exists():
            return None
        try:
            return int(path.read_text().strip())
        except (ValueError, OSError):
            return None

    def is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def is_master_alive(self, host: str) -> bool:
        pid = self.read_pid(host)
        if pid is None:
            return False
        if not self.is_pid_alive(pid):
            self._cleanup_stale(host)
            return False
        return True

    def kill_master(self, host: str) -> bool:
        pid = self.read_pid(host)
        if pid is None:
            return False
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        self._cleanup_stale(host)
        return True

    def get_socket_path(self, host: str) -> Path:
        return socket_path_for(host)

    def socket_exists(self, host: str) -> bool:
        return socket_path_for(host).exists()

    def cleanup_all_stale(self) -> list[str]:
        from sshtm.config.paths import pids_dir

        cleaned: list[str] = []
        pdir = pids_dir()
        if not pdir.exists():
            return cleaned
        for pid_file in pdir.iterdir():
            if not pid_file.suffix == ".pid":
                continue
            try:
                pid = int(pid_file.read_text().strip())
            except (ValueError, OSError):
                pid_file.unlink(missing_ok=True)
                cleaned.append(pid_file.stem)
                continue
            if not self.is_pid_alive(pid):
                host_stem = pid_file.stem
                pid_file.unlink(missing_ok=True)
                socket_file = socket_path_for(host_stem)
                socket_file.unlink(missing_ok=True)
                cleaned.append(host_stem)
        return cleaned

    def _cleanup_stale(self, host: str) -> None:
        pid_path_for(host).unlink(missing_ok=True)
        socket_path_for(host).unlink(missing_ok=True)
