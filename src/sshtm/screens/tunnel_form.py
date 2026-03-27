from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from sshtm.core.ssh_config import SSHConfigParser
from sshtm.core.tunnel import Direction, Tunnel


class TunnelFormScreen(ModalScreen[Tunnel | None]):
    BINDINGS = [
        ("escape", "cancel_form", "Cancel"),
    ]

    def __init__(self, tunnel: Tunnel | None = None) -> None:
        super().__init__()
        self._editing = tunnel
        self._ssh_parser = SSHConfigParser()

    def compose(self) -> ComposeResult:
        hosts = self._ssh_parser.get_hosts()
        host_options: list[tuple[str, str]] = [(h, h) for h in hosts]
        host_options.append(("(manual entry)", "__manual__"))

        direction_options: list[tuple[str, str]] = [
            ("Local → Remote (-L)", "local"),
            ("Remote → Local (-R)", "remote"),
        ]

        title = "Edit Tunnel" if self._editing else "New Tunnel"

        with Vertical(id="tunnel-form-container"):
            yield Static(title)

            with VerticalScroll(id="tunnel-form-scroll"):
                yield Label("SSH Host")
                yield Select(host_options, id="host-select", value=self._editing.ssh_host if self._editing and self._editing.ssh_host in [h for h, _ in host_options[:-1]] else "__manual__")

                yield Label("SSH Host (manual)")
                yield Input(
                    placeholder="user@hostname or ssh-config-host",
                    id="host-manual",
                    value=self._editing.ssh_host if self._editing else "",
                )

                yield Label("Direction")
                yield Select(
                    direction_options,
                    id="direction-select",
                    value=self._editing.direction.value if self._editing else "local",
                )

                yield Label("Local Port")
                yield Input(
                    placeholder="e.g. 8080",
                    id="local-port",
                    value=str(self._editing.local_port) if self._editing else "",
                )

                yield Label("Remote Host")
                yield Input(
                    placeholder="e.g. localhost or db.internal",
                    id="remote-host",
                    value=self._editing.remote_host if self._editing else "localhost",
                )

                yield Label("Remote Port")
                yield Input(
                    placeholder="e.g. 5432",
                    id="remote-port",
                    value=str(self._editing.remote_port) if self._editing else "",
                )

                yield Label("Label (optional)")
                yield Input(
                    placeholder="e.g. prod-db",
                    id="tunnel-label",
                    value=self._editing.label if self._editing else "",
                )

                yield Static("", id="form-error")

            with Horizontal(id="form-buttons"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "host-select":
            manual_input = self.query_one("#host-manual", Input)
            if event.value != "__manual__" and event.value is not Select.BLANK:
                manual_input.value = str(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return

        if event.button.id == "btn-save":
            self._submit_form()

    def _submit_form(self) -> None:
        error_label = self.query_one("#form-error", Static)

        host_select = self.query_one("#host-select", Select)
        manual_host = self.query_one("#host-manual", Input).value.strip()
        direction_val = self.query_one("#direction-select", Select).value
        local_port_str = self.query_one("#local-port", Input).value.strip()
        remote_host = self.query_one("#remote-host", Input).value.strip()
        remote_port_str = self.query_one("#remote-port", Input).value.strip()
        label = self.query_one("#tunnel-label", Input).value.strip()

        if host_select.value and host_select.value != "__manual__" and host_select.value is not Select.BLANK:
            ssh_host = str(host_select.value)
        elif manual_host:
            ssh_host = manual_host
        else:
            error_label.update("[b red]SSH host is required[/]")
            return

        if not local_port_str or not local_port_str.isdigit():
            error_label.update("[b red]Local port must be a number[/]")
            return
        local_port = int(local_port_str)

        if not remote_host:
            remote_host = "localhost"

        if not remote_port_str or not remote_port_str.isdigit():
            error_label.update("[b red]Remote port must be a number[/]")
            return
        remote_port = int(remote_port_str)

        direction = Direction(str(direction_val)) if direction_val and direction_val is not Select.BLANK else Direction.LOCAL

        if self._editing:
            tunnel = Tunnel(
                id=self._editing.id,
                ssh_host=ssh_host,
                local_port=local_port,
                remote_host=remote_host,
                remote_port=remote_port,
                direction=direction,
                label=label,
                enabled=self._editing.enabled,
            )
        else:
            tunnel = Tunnel(
                ssh_host=ssh_host,
                local_port=local_port,
                remote_host=remote_host,
                remote_port=remote_port,
                direction=direction,
                label=label,
            )

        errors = tunnel.validate()
        if errors:
            error_label.update(f"[b red]{errors[0]}[/]")
            return

        self.dismiss(tunnel)

    def action_cancel_form(self) -> None:
        self.dismiss(None)
