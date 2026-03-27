from sshtm.core.tunnel import Direction, Tunnel, TunnelStatus


class TestTunnelCreation:
    def test_create_local_forward(self) -> None:
        tunnel = Tunnel(
            ssh_host="prod-server",
            local_port=8080,
            remote_host="localhost",
            remote_port=5432,
            direction=Direction.LOCAL,
            label="prod-db",
        )
        assert tunnel.ssh_host == "prod-server"
        assert tunnel.local_port == 8080
        assert tunnel.remote_port == 5432
        assert tunnel.direction == Direction.LOCAL
        assert tunnel.status == TunnelStatus.STOPPED

    def test_create_remote_forward(self) -> None:
        tunnel = Tunnel(
            ssh_host="staging",
            local_port=3000,
            remote_host="localhost",
            remote_port=3000,
            direction=Direction.REMOTE,
        )
        assert tunnel.direction == Direction.REMOTE

    def test_auto_generated_id(self) -> None:
        t1 = Tunnel(ssh_host="h", local_port=1, remote_host="r", remote_port=2)
        t2 = Tunnel(ssh_host="h", local_port=1, remote_host="r", remote_port=2)
        assert t1.id != t2.id
        assert len(t1.id) == 12


class TestTunnelForwardSpec:
    def test_local_forward_spec(self) -> None:
        tunnel = Tunnel(
            ssh_host="host",
            local_port=8080,
            remote_host="db.internal",
            remote_port=5432,
            direction=Direction.LOCAL,
        )
        assert tunnel.forward_spec() == "8080:db.internal:5432"
        assert tunnel.ssh_flag() == "-L"

    def test_remote_forward_spec(self) -> None:
        tunnel = Tunnel(
            ssh_host="host",
            local_port=3000,
            remote_host="localhost",
            remote_port=8080,
            direction=Direction.REMOTE,
        )
        assert tunnel.forward_spec() == "8080:localhost:3000"
        assert tunnel.ssh_flag() == "-R"


class TestTunnelDisplayLabel:
    def test_custom_label(self) -> None:
        tunnel = Tunnel(
            ssh_host="h", local_port=1, remote_host="r",
            remote_port=2, label="my-tunnel",
        )
        assert tunnel.display_label() == "my-tunnel"

    def test_auto_label_local(self) -> None:
        tunnel = Tunnel(
            ssh_host="h", local_port=8080, remote_host="db.internal",
            remote_port=5432, direction=Direction.LOCAL,
        )
        assert "8080" in tunnel.display_label()
        assert "→" in tunnel.display_label()

    def test_auto_label_remote(self) -> None:
        tunnel = Tunnel(
            ssh_host="h", local_port=3000, remote_host="localhost",
            remote_port=8080, direction=Direction.REMOTE,
        )
        assert "←" in tunnel.display_label()


class TestTunnelSerialization:
    def test_roundtrip(self) -> None:
        tunnel = Tunnel(
            id="abc123",
            ssh_host="prod",
            local_port=8080,
            remote_host="db.internal",
            remote_port=5432,
            direction=Direction.LOCAL,
            label="prod-db",
            enabled=True,
        )
        data = tunnel.to_dict()
        restored = Tunnel.from_dict(data)
        assert restored.id == tunnel.id
        assert restored.ssh_host == tunnel.ssh_host
        assert restored.local_port == tunnel.local_port
        assert restored.remote_host == tunnel.remote_host
        assert restored.remote_port == tunnel.remote_port
        assert restored.direction == tunnel.direction
        assert restored.label == tunnel.label
        assert restored.enabled == tunnel.enabled

    def test_from_dict_defaults(self) -> None:
        data = {"ssh_host": "host", "local_port": 80, "remote_port": 443}
        tunnel = Tunnel.from_dict(data)
        assert tunnel.remote_host == "localhost"
        assert tunnel.direction == Direction.LOCAL
        assert tunnel.enabled is True


class TestTunnelValidation:
    def test_valid_tunnel(self) -> None:
        tunnel = Tunnel(
            ssh_host="prod", local_port=8080,
            remote_host="localhost", remote_port=5432,
        )
        assert tunnel.validate() == []

    def test_missing_host(self) -> None:
        tunnel = Tunnel(
            ssh_host="", local_port=8080,
            remote_host="localhost", remote_port=5432,
        )
        errors = tunnel.validate()
        assert any("SSH host" in e for e in errors)

    def test_port_out_of_range(self) -> None:
        tunnel = Tunnel(
            ssh_host="h", local_port=99999,
            remote_host="localhost", remote_port=5432,
        )
        errors = tunnel.validate()
        assert any("out of range" in e for e in errors)

    def test_privileged_port_warning(self) -> None:
        tunnel = Tunnel(
            ssh_host="h", local_port=80,
            remote_host="localhost", remote_port=5432,
        )
        errors = tunnel.validate()
        assert any("root" in e.lower() or "privileg" in e.lower() for e in errors)
