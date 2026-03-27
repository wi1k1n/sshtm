from pathlib import Path

from sshtm.config.storage import TunnelStorage
from sshtm.core.tunnel import Direction, Tunnel


class TestTunnelStorageRoundTrip:
    def test_save_and_load(self, tunnels_file: Path, history_file: Path) -> None:
        storage = TunnelStorage(tunnels_file, history_file)
        tunnel = Tunnel(
            ssh_host="prod",
            local_port=8080,
            remote_host="localhost",
            remote_port=5432,
            label="test",
        )
        storage.save_tunnels([tunnel])
        loaded = storage.load_tunnels()
        assert len(loaded) == 1
        assert loaded[0].ssh_host == "prod"
        assert loaded[0].local_port == 8080
        assert loaded[0].label == "test"

    def test_load_empty_file(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        assert storage.load_tunnels() == []

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        storage = TunnelStorage(tmp_path / "nonexistent.toml")
        assert storage.load_tunnels() == []

    def test_multiple_tunnels(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        tunnels = [
            Tunnel(ssh_host="host1", local_port=8080, remote_host="r1", remote_port=80),
            Tunnel(ssh_host="host2", local_port=9090, remote_host="r2", remote_port=443, direction=Direction.REMOTE),
        ]
        storage.save_tunnels(tunnels)
        loaded = storage.load_tunnels()
        assert len(loaded) == 2
        assert loaded[1].direction == Direction.REMOTE


class TestTunnelStorageCRUD:
    def test_add_tunnel(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        t1 = Tunnel(ssh_host="h1", local_port=1, remote_host="r", remote_port=2)
        t2 = Tunnel(ssh_host="h2", local_port=3, remote_host="r", remote_port=4)
        storage.add_tunnel(t1)
        storage.add_tunnel(t2)
        loaded = storage.load_tunnels()
        assert len(loaded) == 2

    def test_remove_tunnel(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        t1 = Tunnel(id="aaa", ssh_host="h1", local_port=1, remote_host="r", remote_port=2)
        t2 = Tunnel(id="bbb", ssh_host="h2", local_port=3, remote_host="r", remote_port=4)
        storage.save_tunnels([t1, t2])
        assert storage.remove_tunnel("aaa") is True
        loaded = storage.load_tunnels()
        assert len(loaded) == 1
        assert loaded[0].id == "bbb"

    def test_remove_nonexistent(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        assert storage.remove_tunnel("doesnt_exist") is False

    def test_update_tunnel(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        tunnel = Tunnel(id="xyz", ssh_host="h", local_port=1, remote_host="r", remote_port=2, label="old")
        storage.save_tunnels([tunnel])
        tunnel.label = "new"
        assert storage.update_tunnel(tunnel) is True
        loaded = storage.load_tunnels()
        assert loaded[0].label == "new"


class TestAtomicWrite:
    def test_file_exists_after_save(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        storage.save_tunnels([])
        assert tunnels_file.exists()

    def test_no_tmp_files_left(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file)
        tunnel = Tunnel(ssh_host="h", local_port=1, remote_host="r", remote_port=2)
        storage.save_tunnels([tunnel])
        parent = tunnels_file.parent
        tmp_files = [f for f in parent.iterdir() if f.suffix == ".tmp"]
        assert len(tmp_files) == 0


class TestHistory:
    def test_add_and_load_history(self, tunnels_file: Path, history_file: Path) -> None:
        storage = TunnelStorage(tunnels_file, history_file)
        tunnel = Tunnel(ssh_host="h", local_port=8080, remote_host="r", remote_port=5432)
        storage.add_history_entry(tunnel)
        history = storage.load_history()
        assert len(history) == 1
        assert history[0]["ssh_host"] == "h"

    def test_history_deduplication(self, tunnels_file: Path, history_file: Path) -> None:
        storage = TunnelStorage(tunnels_file, history_file)
        tunnel = Tunnel(ssh_host="h", local_port=8080, remote_host="r", remote_port=5432, direction=Direction.LOCAL)
        storage.add_history_entry(tunnel)
        storage.add_history_entry(tunnel)
        history = storage.load_history()
        assert len(history) == 1

    def test_history_without_path(self, tunnels_file: Path) -> None:
        storage = TunnelStorage(tunnels_file, history_path=None)
        tunnel = Tunnel(ssh_host="h", local_port=1, remote_host="r", remote_port=2)
        storage.add_history_entry(tunnel)
        assert storage.load_history() == []
