import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    config_dir = tmp_path / "sshtm"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tunnels_file(tmp_config_dir: Path) -> Path:
    return tmp_config_dir / "tunnels.toml"


@pytest.fixture
def history_file(tmp_config_dir: Path) -> Path:
    return tmp_config_dir / "history.toml"


@pytest.fixture(autouse=True)
def override_config_dir(tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_config_dir.parent))


@pytest.fixture
def ssh_config_path() -> Path:
    return Path(__file__).parent / "fixtures" / "ssh_config_simple"
