from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Self


class Direction(Enum):
    LOCAL = "local"
    REMOTE = "remote"


class TunnelStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class Tunnel:
    ssh_host: str
    local_port: int
    remote_host: str
    remote_port: int
    direction: Direction = Direction.LOCAL
    label: str = ""
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: TunnelStatus = field(default=TunnelStatus.STOPPED, repr=False)
    error_message: str = field(default="", repr=False)

    def forward_spec(self) -> str:
        if self.direction == Direction.LOCAL:
            return f"{self.local_port}:{self.remote_host}:{self.remote_port}"
        return f"{self.remote_port}:{self.remote_host}:{self.local_port}"

    def ssh_flag(self) -> str:
        return "-L" if self.direction == Direction.LOCAL else "-R"

    def display_label(self) -> str:
        if self.label:
            return self.label
        arrow = "→" if self.direction == Direction.LOCAL else "←"
        return f"{self.local_port} {arrow} {self.remote_host}:{self.remote_port}"

    def to_dict(self) -> dict[str, str | int | bool]:
        return {
            "id": self.id,
            "ssh_host": self.ssh_host,
            "local_port": self.local_port,
            "remote_host": self.remote_host,
            "remote_port": self.remote_port,
            "direction": self.direction.value,
            "label": self.label,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | int | bool]) -> Self:
        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            ssh_host=str(data["ssh_host"]),
            local_port=int(data["local_port"]),
            remote_host=str(data.get("remote_host", "localhost")),
            remote_port=int(data["remote_port"]),
            direction=Direction(str(data.get("direction", "local"))),
            label=str(data.get("label", "")),
            enabled=bool(data.get("enabled", True)),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.ssh_host:
            errors.append("SSH host is required")
        if not 1 <= self.local_port <= 65535:
            errors.append(f"Local port {self.local_port} out of range (1-65535)")
        if not 1 <= self.remote_port <= 65535:
            errors.append(f"Remote port {self.remote_port} out of range (1-65535)")
        if not self.remote_host:
            errors.append("Remote host is required")
        if self.local_port < 1024:
            errors.append(f"Local port {self.local_port} requires root privileges")
        return errors
