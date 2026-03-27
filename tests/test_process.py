import os
from pathlib import Path
from unittest.mock import patch

from sshtm.core.process import ProcessTracker


class TestProcessTracker:
    def test_write_and_read_pid(self, tmp_config_dir: Path) -> None:
        tracker = ProcessTracker()
        tracker.write_pid("testhost", 12345)
        assert tracker.read_pid("testhost") == 12345

    def test_read_nonexistent_pid(self) -> None:
        tracker = ProcessTracker()
        assert tracker.read_pid("nonexistent-host-xyz") is None

    def test_is_pid_alive_current_process(self) -> None:
        tracker = ProcessTracker()
        assert tracker.is_pid_alive(os.getpid()) is True

    def test_is_pid_alive_dead_process(self) -> None:
        tracker = ProcessTracker()
        assert tracker.is_pid_alive(999999999) is False

    def test_is_master_alive_no_pid_file(self) -> None:
        tracker = ProcessTracker()
        assert tracker.is_master_alive("nonexistent-host-abc") is False

    def test_is_master_alive_with_running_process(self, tmp_config_dir: Path) -> None:
        tracker = ProcessTracker()
        tracker.write_pid("livehost", os.getpid())
        assert tracker.is_master_alive("livehost") is True

    def test_is_master_alive_cleans_stale(self, tmp_config_dir: Path) -> None:
        tracker = ProcessTracker()
        tracker.write_pid("deadhost", 999999999)
        assert tracker.is_master_alive("deadhost") is False
        assert tracker.read_pid("deadhost") is None

    def test_socket_exists(self, tmp_config_dir: Path) -> None:
        tracker = ProcessTracker()
        sock_path = tracker.get_socket_path("somehost")
        assert not tracker.socket_exists("somehost")
        sock_path.parent.mkdir(parents=True, exist_ok=True)
        sock_path.touch()
        assert tracker.socket_exists("somehost")

    def test_cleanup_all_stale(self, tmp_config_dir: Path) -> None:
        tracker = ProcessTracker()
        tracker.write_pid("dead1", 999999998)
        tracker.write_pid("dead2", 999999997)
        tracker.write_pid("alive", os.getpid())
        cleaned = tracker.cleanup_all_stale()
        assert len(cleaned) >= 2
        assert tracker.read_pid("alive") == os.getpid()
