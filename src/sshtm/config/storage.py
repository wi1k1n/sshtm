from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path

import tomli_w

from sshtm.core.tunnel import Tunnel


class TunnelStorage:
    def __init__(self, tunnels_path: Path, history_path: Path | None = None) -> None:
        self._tunnels_path = tunnels_path
        self._history_path = history_path

    def _atomic_write(self, path: Path, data: dict[str, list[dict[str, str | int | bool]]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), prefix=".sshtm_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as f:
                tomli_w.dump(data, f)
            os.replace(tmp, str(path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _read_toml(self, path: Path) -> dict[str, list[dict[str, str | int | bool]]]:
        if not path.exists():
            return {}
        with open(path, "rb") as f:
            return tomllib.load(f)

    def load_tunnels(self) -> list[Tunnel]:
        data = self._read_toml(self._tunnels_path)
        tunnels: list[Tunnel] = []
        for entry in data.get("tunnels", []):
            try:
                tunnels.append(Tunnel.from_dict(entry))
            except (KeyError, ValueError):
                continue
        return tunnels

    def save_tunnels(self, tunnels: list[Tunnel]) -> None:
        data = {"tunnels": [t.to_dict() for t in tunnels]}
        self._atomic_write(self._tunnels_path, data)

    def add_tunnel(self, tunnel: Tunnel) -> None:
        tunnels = self.load_tunnels()
        tunnels.append(tunnel)
        self.save_tunnels(tunnels)

    def remove_tunnel(self, tunnel_id: str) -> bool:
        tunnels = self.load_tunnels()
        before = len(tunnels)
        tunnels = [t for t in tunnels if t.id != tunnel_id]
        if len(tunnels) < before:
            self.save_tunnels(tunnels)
            return True
        return False

    def update_tunnel(self, tunnel: Tunnel) -> bool:
        tunnels = self.load_tunnels()
        for i, t in enumerate(tunnels):
            if t.id == tunnel.id:
                tunnels[i] = tunnel
                self.save_tunnels(tunnels)
                return True
        return False

    def load_history(self) -> list[dict[str, str | int]]:
        if not self._history_path:
            return []
        data = self._read_toml(self._history_path)
        return list(data.get("history", []))

    def add_history_entry(self, tunnel: Tunnel) -> None:
        if not self._history_path:
            return
        history = self.load_history()
        entry = tunnel.to_dict()
        # Deduplicate by matching host+ports+direction
        history = [
            h
            for h in history
            if not (
                h.get("ssh_host") == entry["ssh_host"]
                and h.get("local_port") == entry["local_port"]
                and h.get("remote_port") == entry["remote_port"]
                and h.get("direction") == entry["direction"]
            )
        ]
        history.insert(0, entry)
        history = history[:50]
        self._atomic_write(self._history_path, {"history": history})
