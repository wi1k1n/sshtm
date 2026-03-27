from unittest.mock import MagicMock, patch
import subprocess

from sshtm.core.health import check_master_alive, is_port_available, is_port_reachable


class TestPortAvailability:
    def test_available_port(self) -> None:
        assert is_port_available(59999) is True

    def test_unavailable_port(self) -> None:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 59998))
            s.listen(1)
            assert is_port_available(59998) is False


class TestPortReachable:
    def test_reachable_port(self) -> None:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 59997))
            s.listen(1)
            assert is_port_reachable(59997, timeout=1.0) is True

    def test_unreachable_port(self) -> None:
        assert is_port_reachable(59996, timeout=0.5) is False


class TestCheckMasterAlive:
    @patch("sshtm.core.health.subprocess.run")
    def test_master_alive(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert check_master_alive("/tmp/test.sock", "testhost") is True

    @patch("sshtm.core.health.subprocess.run")
    def test_master_dead(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=255)
        assert check_master_alive("/tmp/test.sock", "testhost") is False

    @patch("sshtm.core.health.subprocess.run")
    def test_master_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired("ssh", 5)
        assert check_master_alive("/tmp/test.sock", "testhost") is False
