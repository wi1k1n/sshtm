from unittest.mock import MagicMock, patch
import subprocess

from sshtm.core.manager import TunnelManager
from sshtm.core.tunnel import Direction, Tunnel, TunnelStatus


class TestTunnelManagerStartTunnel:
    @patch("sshtm.core.manager.subprocess.run")
    @patch("sshtm.core.manager.is_port_available", return_value=True)
    @patch("sshtm.core.manager.check_master_alive", return_value=False)
    @patch("sshtm.core.manager.socket_path_for")
    def test_start_creates_master_and_forward(
        self,
        mock_socket_path: MagicMock,
        mock_master_alive: MagicMock,
        mock_port_available: MagicMock,
        mock_run: MagicMock,
        tmp_config_dir,
    ) -> None:
        mock_sock = tmp_config_dir / "sockets" / "test.sock"
        mock_sock.parent.mkdir(parents=True, exist_ok=True)
        mock_socket_path.return_value = mock_sock

        def run_side_effect(cmd, **kwargs):
            if "-O" not in cmd and "ControlMaster=yes" in cmd:
                mock_sock.touch()
            result = MagicMock(returncode=0, stderr="Master running (pid=1234)")
            return result

        mock_run.side_effect = run_side_effect

        manager = TunnelManager()
        tunnel = Tunnel(
            ssh_host="test",
            local_port=8080,
            remote_host="localhost",
            remote_port=5432,
        )
        success, msg = manager.start_tunnel(tunnel)
        assert success is True

    @patch("sshtm.core.manager.is_port_available", return_value=False)
    def test_start_fails_on_port_conflict(self, mock_port: MagicMock) -> None:
        manager = TunnelManager()
        tunnel = Tunnel(
            ssh_host="test",
            local_port=8080,
            remote_host="localhost",
            remote_port=5432,
        )
        success, msg = manager.start_tunnel(tunnel)
        assert success is False
        assert "already in use" in msg


class TestTunnelManagerHealthCheck:
    @patch("sshtm.core.manager.is_port_reachable", return_value=True)
    @patch("sshtm.core.manager.check_master_alive", return_value=True)
    @patch("sshtm.core.manager.socket_path_for")
    def test_running_tunnel(
        self,
        mock_socket_path: MagicMock,
        mock_master: MagicMock,
        mock_port: MagicMock,
        tmp_config_dir,
    ) -> None:
        mock_sock = tmp_config_dir / "sockets" / "test.sock"
        mock_sock.parent.mkdir(parents=True, exist_ok=True)
        mock_sock.touch()
        mock_socket_path.return_value = mock_sock

        manager = TunnelManager()
        tunnel = Tunnel(
            ssh_host="test",
            local_port=8080,
            remote_host="localhost",
            remote_port=5432,
        )
        status = manager.check_tunnel_health(tunnel)
        assert status == TunnelStatus.RUNNING

    @patch("sshtm.core.manager.socket_path_for")
    def test_stopped_tunnel_no_socket(self, mock_socket_path: MagicMock, tmp_config_dir) -> None:
        mock_sock = tmp_config_dir / "sockets" / "missing.sock"
        mock_socket_path.return_value = mock_sock

        manager = TunnelManager()
        tunnel = Tunnel(
            ssh_host="test",
            local_port=8080,
            remote_host="localhost",
            remote_port=5432,
        )
        status = manager.check_tunnel_health(tunnel)
        assert status == TunnelStatus.STOPPED


class TestTunnelManagerForwardCommands:
    @patch("sshtm.core.manager.subprocess.run")
    @patch("sshtm.core.manager.socket_path_for")
    def test_add_forward_command(self, mock_socket_path: MagicMock, mock_run: MagicMock, tmp_config_dir) -> None:
        mock_sock = tmp_config_dir / "test.sock"
        mock_sock.touch()
        mock_socket_path.return_value = mock_sock
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        manager = TunnelManager()
        tunnel = Tunnel(
            ssh_host="myhost",
            local_port=8080,
            remote_host="db.internal",
            remote_port=5432,
            direction=Direction.LOCAL,
        )
        success, msg = manager._add_forward(tunnel)
        assert success is True

        call_args = mock_run.call_args[0][0]
        assert "-O" in call_args
        assert "forward" in call_args
        assert "-L" in call_args
        assert "8080:db.internal:5432" in call_args

    @patch("sshtm.core.manager.subprocess.run")
    @patch("sshtm.core.manager.socket_path_for")
    def test_cancel_forward_command(self, mock_socket_path: MagicMock, mock_run: MagicMock, tmp_config_dir) -> None:
        mock_sock = tmp_config_dir / "test.sock"
        mock_sock.touch()
        mock_socket_path.return_value = mock_sock
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        manager = TunnelManager()
        tunnel = Tunnel(
            ssh_host="myhost",
            local_port=8080,
            remote_host="db.internal",
            remote_port=5432,
            direction=Direction.REMOTE,
        )
        success, msg = manager._cancel_forward(tunnel)
        assert success is True

        call_args = mock_run.call_args[0][0]
        assert "cancel" in call_args
        assert "-R" in call_args
