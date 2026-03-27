from pathlib import Path

from sshtm.core.ssh_config import SSHConfigParser


class TestSSHConfigParser:
    def test_get_hosts(self, ssh_config_path: Path) -> None:
        parser = SSHConfigParser(ssh_config_path)
        hosts = parser.get_hosts()
        assert "prod-server" in hosts
        assert "staging" in hosts
        assert "dev-box" in hosts
        assert "*" not in hosts

    def test_get_host_info(self, ssh_config_path: Path) -> None:
        parser = SSHConfigParser(ssh_config_path)
        info = parser.get_host_info("prod-server")
        assert info is not None
        assert info.hostname == "192.168.1.100"
        assert info.user == "admin"
        assert info.port == 22

    def test_get_host_info_custom_port(self, ssh_config_path: Path) -> None:
        parser = SSHConfigParser(ssh_config_path)
        info = parser.get_host_info("staging")
        assert info is not None
        assert info.hostname == "staging.example.com"
        assert info.port == 2222
        assert info.user == "deploy"

    def test_get_host_info_unknown(self, ssh_config_path: Path) -> None:
        parser = SSHConfigParser(ssh_config_path)
        info = parser.get_host_info("nonexistent-host")
        assert info is None

    def test_nonexistent_config_file(self, tmp_path: Path) -> None:
        parser = SSHConfigParser(tmp_path / "nonexistent_config")
        assert parser.get_hosts() == []

    def test_reload(self, ssh_config_path: Path) -> None:
        parser = SSHConfigParser(ssh_config_path)
        hosts_before = parser.get_hosts()
        parser.reload()
        hosts_after = parser.get_hosts()
        assert hosts_before == hosts_after
