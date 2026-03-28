from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from sshtm.core.tunnel import Tunnel, TunnelStatus
from sshtm.widgets.tunnel_table import TunnelTable

STATUS_INDICATORS = {
    TunnelStatus.STOPPED: ("●", "red"),
    TunnelStatus.STARTING: ("◐", "yellow"),
    TunnelStatus.RUNNING: ("●", "green"),
    TunnelStatus.ERROR: ("✖", "red"),
}


class MainScreen(Vertical):
    def compose(self) -> ComposeResult:
        table = TunnelTable(id="tunnel-table", cursor_type="row", cursor_foreground_priority="renderable")
        yield table
        yield Static("", id="status-bar")

    def on_mount(self) -> None:
        table = self.query_one("#tunnel-table", TunnelTable)
        table.add_columns("", "Label", "Dir", "Local Port", "Remote", "SSH Host", "Status")
        self._update_status_bar()

    def refresh_tunnels(self, tunnels: list[Tunnel]) -> None:
        table = self.query_one("#tunnel-table", TunnelTable)
        was_active = table._selection_active
        cursor_row = table.cursor_row

        table.clear()
        for tunnel in tunnels:
            indicator, color = STATUS_INDICATORS.get(
                tunnel.status, ("?", "white")
            )
            status_text = f"[{color}]{indicator}[/{color}]"
            direction = "L\u2192R" if tunnel.direction.value == "local" else "R\u2192L"
            table.add_row(
                status_text,
                tunnel.display_label(),
                direction,
                str(tunnel.local_port),
                f"{tunnel.remote_host}:{tunnel.remote_port}",
                tunnel.ssh_host,
                tunnel.status.value,
                key=tunnel.id,
            )

        if tunnels and was_active:
            table._enter_selected(min(cursor_row, len(tunnels) - 1))
        elif tunnels and not was_active:
            table._enter_unselected()

        self._update_status_bar(len(tunnels))

    def get_selected_tunnel(self, tunnels: list[Tunnel]) -> Tunnel | None:
        table = self.query_one("#tunnel-table", TunnelTable)
        if table.row_count == 0 or not table.selection_active:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        for tunnel in tunnels:
            if tunnel.id == row_key.value:
                return tunnel
        return None

    def _update_status_bar(self, count: int = 0) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.update(
            f" {count} tunnel(s) │ "
            "[b]n[/b]ew  [b]s[/b]tart/stop  [b]e[/b]dit  [b]d[/b]elete  "
            "[b]i[/b]nfo  [b]l[/b]og  [b]r[/b]efresh  [b]?[/b]help  [b]q[/b]uit"
        )


class ConfirmDialog(ModalScreen[bool]):
    BINDINGS = [
        ("escape", "cancel_dialog", "Cancel"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical
        with Vertical(id="confirm-container"):
            yield Static(self._message)
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", variant="error", id="confirm-yes")
                yield Button("No", variant="primary", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_cancel_dialog(self) -> None:
        self.dismiss(False)


class ErrorDetailScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss_screen", "Close"),
    ]

    def __init__(self, tunnel: Tunnel) -> None:
        super().__init__()
        self._tunnel = tunnel

    def compose(self) -> ComposeResult:
        t = self._tunnel
        status_line = f"[b]Status:[/b] {t.status.value}"
        direction = "Local \u2192 Remote (-L)" if t.direction.value == "local" else "Remote \u2192 Local (-R)"
        details = (
            f"[b]Label:[/b]       {t.display_label()}\n"
            f"[b]SSH Host:[/b]    {t.ssh_host}\n"
            f"[b]Direction:[/b]   {direction}\n"
            f"[b]Local Port:[/b]  {t.local_port}\n"
            f"[b]Remote:[/b]      {t.remote_host}:{t.remote_port}\n"
            f"\n{status_line}"
        )
        if t.error_message:
            details += f"\n\n[b red]Error:[/b red] {t.error_message}"

        with Vertical(id="info-container"):
            yield Static("Tunnel Info", id="info-title")
            yield Static(details)
            yield Button("Close", variant="primary", id="info-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "info-close":
            self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()


class LogViewScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss_screen", "Close"),
    ]

    def __init__(self, ssh_host: str, log_text: str) -> None:
        super().__init__()
        self._ssh_host = ssh_host
        self._log_text = log_text

    def compose(self) -> ComposeResult:
        with Vertical(id="log-container"):
            yield Static(f"SSH Log: {self._ssh_host}", id="log-title")
            with VerticalScroll(id="log-scroll"):
                yield Static(self._log_text, id="log-content")
            yield Button("Close", variant="primary", id="log-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-close":
            self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
