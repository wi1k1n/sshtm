from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sshconf import read_ssh_config


@dataclass
class HostInfo:
    name: str
    hostname: str
    port: int
    user: str
    identity_file: str


class SSHConfigParser:
    def __init__(self, config_path: str | Path | None = None) -> None:
        self._path = Path(config_path) if config_path else Path.home() / ".ssh" / "config"
        self._config = None
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._config = read_ssh_config(str(self._path))
            except Exception:
                self._config = None
        else:
            self._config = None

    def get_hosts(self) -> list[str]:
        if self._config is None:
            return []
        try:
            hosts = self._config.hosts()
        except Exception:
            return []
        return [h for h in hosts if h != "*" and not h.startswith("!")]

    def get_host_info(self, host: str) -> HostInfo | None:
        if self._config is None:
            return None
        if host not in self.get_hosts():
            return None
        try:
            params = self._config.host(host)
        except KeyError:
            return None
        return HostInfo(
            name=host,
            hostname=params.get("hostname", host),
            port=int(params.get("port", 22)),
            user=params.get("user", ""),
            identity_file=params.get("identityfile", ""),
        )

    def reload(self) -> None:
        self._load()
